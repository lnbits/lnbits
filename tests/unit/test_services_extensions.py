from uuid import uuid4
from types import SimpleNamespace

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import (
    create_installed_extension,
    delete_installed_extension,
    get_installed_extension,
    get_installed_extensions,
)
from lnbits.core.models.extensions import (
    Extension,
    ExtensionMeta,
    ExtensionRelease,
    InstallableExtension,
    ReleasePaymentInfo,
)
from lnbits.core.services.extensions import (
    activate_extension,
    deactivate_extension,
    get_valid_extension,
    get_valid_extensions,
    install_extension,
    start_extension_background_work,
    stop_extension_background_work,
    uninstall_extension,
)
from lnbits.settings import Settings


def _installable_extension(
    ext_id: str,
    version: str = "1.0.0",
    compatible: bool = True,
    *,
    payments: list[ReleasePaymentInfo] | None = None,
) -> InstallableExtension:
    return InstallableExtension(
        id=ext_id,
        name=f"Extension {ext_id}",
        version=version,
        short_description="Demo extension",
        meta=ExtensionMeta(
            installed_release=ExtensionRelease(
                name=ext_id,
                version=version,
                archive=f"https://example.com/{ext_id}.zip",
                source_repo="org/repo",
                hash=f"hash-{ext_id}",
                is_version_compatible=compatible,
            ),
            payments=payments or [],
        ),
    )


@pytest.mark.anyio
async def test_install_extension_rejects_incompatible_release(tmp_path, settings: Settings):
    ext_info = _installable_extension(f"ext_{uuid4().hex[:8]}", compatible=False)
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        with pytest.raises(ValueError, match="Incompatible extension version"):
            await install_extension(ext_info)
    finally:
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path


@pytest.mark.anyio
async def test_install_extension_creates_new_extension_and_starts_background_work(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = _installable_extension(ext_id)
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    download_mock = mocker.patch.object(
        InstallableExtension, "download_archive", mocker.AsyncMock()
    )
    extract_mock = mocker.patch.object(InstallableExtension, "extract_archive")
    start_mock = mocker.patch(
        "lnbits.core.services.extensions.start_extension_background_work",
        mocker.AsyncMock(return_value=True),
    )
    mocker.patch(
        "lnbits.core.services.extensions.get_db_version",
        mocker.AsyncMock(return_value=0),
    )
    mocker.patch(
        "lnbits.core.services.extensions.migrate_extension_database",
        mocker.AsyncMock(),
    )

    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        extension = await install_extension(ext_info)
        stored = await get_installed_extension(ext_id)
    finally:
        await delete_installed_extension(ext_id=ext_id)
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path

    assert extension.code == ext_id
    assert stored is not None
    download_mock.assert_awaited_once()
    extract_mock.assert_called_once()
    start_mock.assert_awaited_once_with(ext_id)


@pytest.mark.anyio
async def test_install_extension_updates_existing_upgrade_and_preserves_payments(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    ext_id = f"ext_{uuid4().hex[:8]}"
    existing_payment = ReleasePaymentInfo(
        pay_link="https://pay.example",
        payment_hash="payment-hash",
    )
    existing_ext = _installable_extension(ext_id, payments=[existing_payment])
    updated_ext = _installable_extension(ext_id, version="2.0.0")
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    extract_mock = mocker.patch.object(InstallableExtension, "extract_archive")
    start_mock = mocker.patch(
        "lnbits.core.services.extensions.start_extension_background_work",
        mocker.AsyncMock(return_value=True),
    )
    stop_mock = mocker.patch(
        "lnbits.core.services.extensions.stop_extension_background_work",
        mocker.AsyncMock(return_value=True),
    )
    mocker.patch(
        "lnbits.core.services.extensions.get_db_version",
        mocker.AsyncMock(return_value=1),
    )
    mocker.patch(
        "lnbits.core.services.extensions.migrate_extension_database",
        mocker.AsyncMock(),
    )

    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        await create_installed_extension(existing_ext)
        updated_ext.ext_upgrade_dir.mkdir(parents=True, exist_ok=True)

        extension = await install_extension(updated_ext, skip_download=True)
        stored = await get_installed_extension(ext_id)
    finally:
        await delete_installed_extension(ext_id=ext_id)
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path

    assert extension.code == ext_id
    assert extension.is_upgrade_extension is True
    assert stored is not None
    assert stored.meta is not None
    assert stored.meta.payments == [existing_payment]
    extract_mock.assert_called_once()
    stop_mock.assert_awaited_once_with(ext_id)
    start_mock.assert_awaited_once_with(ext_id)


@pytest.mark.anyio
async def test_uninstall_activate_and_deactivate_extensions(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = _installable_extension(ext_id)
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    original_deactivated = set(settings.lnbits_deactivated_extensions)
    stop_mock = mocker.patch(
        "lnbits.core.services.extensions.stop_extension_background_work",
        mocker.AsyncMock(return_value=True),
    )
    start_mock = mocker.patch(
        "lnbits.core.services.extensions.start_extension_background_work",
        mocker.AsyncMock(return_value=True),
    )
    clean_mock = mocker.patch.object(InstallableExtension, "clean_extension_files")
    register_routes_mock = mocker.patch(
        "lnbits.core.services.extensions.core_app_extra.register_new_ext_routes"
    )

    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        await create_installed_extension(ext_info)

        await uninstall_extension(ext_id)
        assert await get_installed_extension(ext_id) is None
        assert ext_id in settings.lnbits_deactivated_extensions

        await create_installed_extension(ext_info)
        await activate_extension(Extension(code=ext_id, is_valid=True))
        active_ext = await get_installed_extension(ext_id)
        assert active_ext is not None
        assert active_ext.active is True

        await deactivate_extension(ext_id)
        inactive_ext = await get_installed_extension(ext_id)
        assert inactive_ext is not None
        assert inactive_ext.active is False
        assert ext_id in settings.lnbits_deactivated_extensions
    finally:
        await delete_installed_extension(ext_id=ext_id)
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_deactivated_extensions = original_deactivated

    clean_mock.assert_called_once()
    register_routes_mock.assert_called_once()
    assert stop_mock.await_count == 2
    assert start_mock.await_count == 1


@pytest.mark.anyio
async def test_stop_extension_background_work_handles_missing_and_async_stops(
    mocker: MockerFixture,
):
    import_module_mock = mocker.patch(
        "lnbits.core.services.extensions.importlib.import_module",
        return_value=object(),
    )

    assert await stop_extension_background_work("demoext") is False

    called = {"stop": False}

    async def demoext_stop():
        called["stop"] = True

    import_module_mock.return_value = SimpleNamespace(demoext_stop=demoext_stop)

    assert await stop_extension_background_work("demoext") is True
    assert called["stop"] is True


@pytest.mark.anyio
async def test_start_extension_background_work_handles_missing_and_sync_starts(
    mocker: MockerFixture,
):
    import_module_mock = mocker.patch(
        "lnbits.core.services.extensions.importlib.import_module",
        return_value=object(),
    )

    assert await start_extension_background_work("demoext") is False

    called = {"start": False}

    def demoext_start():
        called["start"] = True

    import_module_mock.return_value = SimpleNamespace(demoext_start=demoext_start)

    assert await start_extension_background_work("demoext") is True
    assert called["start"] is True


@pytest.mark.anyio
async def test_get_valid_extensions_and_single_extension_respect_settings(
    tmp_path, settings: Settings
):
    ext_id_one = f"ext_{uuid4().hex[:8]}"
    ext_id_two = f"ext_{uuid4().hex[:8]}"
    ext_one = _installable_extension(ext_id_one)
    ext_two = _installable_extension(ext_id_two)
    original_deactivated = set(settings.lnbits_deactivated_extensions)
    original_deactivate_all = settings.lnbits_extensions_deactivate_all
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path

    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        settings.lnbits_deactivated_extensions = {ext_id_two}
        settings.lnbits_extensions_deactivate_all = False
        await create_installed_extension(ext_one)
        await create_installed_extension(ext_two)

        valid_extensions = await get_valid_extensions(include_deactivated=False)
        valid_codes = {ext.code for ext in valid_extensions}
        assert ext_id_one in valid_codes
        assert ext_id_two not in valid_codes

        assert await get_valid_extension(ext_id_one, include_deactivated=True) is not None

        settings.lnbits_extensions_deactivate_all = True
        assert await get_valid_extensions(include_deactivated=False) == []
        assert await get_valid_extension(ext_id_one, include_deactivated=False) is None
    finally:
        await delete_installed_extension(ext_id=ext_id_one)
        await delete_installed_extension(ext_id=ext_id_two)
        settings.lnbits_deactivated_extensions = original_deactivated
        settings.lnbits_extensions_deactivate_all = original_deactivate_all
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path
