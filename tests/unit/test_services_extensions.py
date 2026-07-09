from types import SimpleNamespace
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import (
    create_installed_extension,
    delete_installed_extension,
    get_installed_extension,
)
from lnbits.core.models.extensions import (
    Extension,
    InstallableExtension,
    ReleasePaymentInfo,
)
from lnbits.core.services import extensions as extension_services
from lnbits.core.services.extensions import (
    activate_extension,
    attach_wasm_invocation_runtime,
    deactivate_extension,
    finish_wasm_invocation,
    get_current_wasm_invocations,
    get_valid_extension,
    get_valid_extensions,
    install_extension,
    record_wasm_invocation_host_call,
    start_extension_background_work,
    start_wasm_invocation,
    stop_extension_background_work,
    stop_wasm_invocation,
    uninstall_extension,
)
from lnbits.settings import Settings
from tests.helpers import make_installable_extension


@pytest.mark.anyio
async def test_install_extension_rejects_incompatible_release(
    tmp_path, settings: Settings
):
    ext_info = make_installable_extension(f"ext_{uuid4().hex[:8]}", compatible=False)
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
    ext_info = make_installable_extension(ext_id)
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
    existing_ext = make_installable_extension(ext_id, payments=[existing_payment])
    updated_ext = make_installable_extension(ext_id, version="2.0.0")
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
    ext_info = make_installable_extension(ext_id)
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
async def test_wasm_invocation_tracking_counts_and_stops(mocker: MockerFixture):
    _reset_wasm_invocation_state()
    mocker.patch(
        "lnbits.core.services.extensions.create_wasm_invocation",
        mocker.AsyncMock(),
    )
    update_mock = mocker.patch(
        "lnbits.core.services.extensions.update_wasm_invocation",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.get_wasm_invocation",
        mocker.AsyncMock(return_value=None),
    )
    mocker.patch(
        "lnbits.core.services.extensions.mark_stale_wasm_invocations",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.delete_old_wasm_invocations",
        mocker.AsyncMock(),
    )

    invocation = await start_wasm_invocation(
        extension_id="demoext",
        export_name="render",
        trigger_type="http",
        method="POST",
        path="/api/v1/ext/demoext/run",
        context={"origin": "https://example.com"},
    )
    store = SimpleNamespace(deadline=None)
    store.set_epoch_deadline = lambda deadline: setattr(store, "deadline", deadline)
    engine = SimpleNamespace(increments=0)

    def increment_epoch():
        engine.increments += 1

    engine.increment_epoch = increment_epoch

    attach_wasm_invocation_runtime(invocation.id, engine=engine, store=store)
    record_wasm_invocation_host_call(invocation.id, "http.request")
    record_wasm_invocation_host_call(invocation.id, "storage.get")

    assert await stop_wasm_invocation(invocation.id, reason="test stop") is True
    current = get_current_wasm_invocations()
    assert current[0].status == "stopping"
    assert store.deadline == 1
    assert engine.increments == 1

    await finish_wasm_invocation(invocation.id, status="failed")
    assert update_mock.await_args is not None
    saved = update_mock.await_args.args[0]
    assert saved.status == "stopped"
    assert saved.stop_reason == "test stop"
    assert saved.host_call_count == 2
    assert saved.http_call_count == 1
    assert saved.storage_call_count == 1


def _reset_wasm_invocation_state():
    with extension_services._wasm_invocation_lock:
        extension_services._wasm_invocation_handles.clear()
        extension_services._wasm_invocations_marked_stale = False
        extension_services._wasm_invocations_last_cleanup_at = None


def test_wasm_runtime_limits_merge_sparse_extension_overrides(settings: Settings):
    original_execution_ms = settings.wasm_runtime_max_execution_ms
    original_memory_bytes = settings.wasm_runtime_max_memory_bytes
    try:
        settings.wasm_runtime_max_execution_ms = 5_000
        settings.wasm_runtime_max_memory_bytes = 64 * 1024 * 1024
        extension = InstallableExtension(
            id="wasm_demo",
            name="WASM Demo",
            version="1.0.0",
            wasm_runtime_limits={
                "wasm_runtime_max_execution_ms": 20_000,
                "wasm_runtime_max_fuel": 0,
            },
        )

        limits = extension_services.resolve_wasm_runtime_limits(extension)

        assert limits["wasm_runtime_max_execution_ms"] == 20_000
        assert limits["wasm_runtime_max_fuel"] == 0
        assert limits["wasm_runtime_max_memory_bytes"] == 64 * 1024 * 1024
    finally:
        settings.wasm_runtime_max_execution_ms = original_execution_ms
        settings.wasm_runtime_max_memory_bytes = original_memory_bytes


def test_wasm_runtime_limit_override_validation():
    assert extension_services.validate_wasm_runtime_limit_overrides(
        {
            "wasm_runtime_max_execution_ms": "7000",
            "wasm_runtime_max_fuel": 0,
            "wasm_runtime_max_memory_bytes": "",
        }
    ) == {
        "wasm_runtime_max_execution_ms": 7000,
        "wasm_runtime_max_fuel": 0,
    }

    with pytest.raises(ValueError, match="Unknown WASM runtime limit field"):
        extension_services.validate_wasm_runtime_limit_overrides({"unknown": 1})

    with pytest.raises(ValueError, match="cannot be negative"):
        extension_services.validate_wasm_runtime_limit_overrides(
            {"wasm_runtime_max_execution_ms": -1}
        )

    with pytest.raises(ValueError, match="must be an integer"):
        extension_services.validate_wasm_runtime_limit_overrides(
            {"wasm_runtime_max_execution_ms": True}
        )

    with pytest.raises(ValueError, match="must be an integer"):
        extension_services.validate_wasm_runtime_limit_overrides(
            {"wasm_runtime_max_execution_ms": 1.5}
        )


@pytest.mark.anyio
async def test_update_wasm_extension_runtime_limits_saves_sparse_overrides(
    tmp_path,
    settings: Settings,
    mocker: MockerFixture,
):
    ext_id = "wasm_demo"
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_extensions_path = str(tmp_path)
        config_dir = tmp_path / "extensions" / ext_id
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text(
            '{"extension_type": "wasm"}',
            encoding="utf-8",
        )
        installed_extension = InstallableExtension(
            id=ext_id,
            name="WASM Demo",
            version="1.0.0",
        )
        mocker.patch(
            "lnbits.core.services.extensions.get_installed_extension",
            mocker.AsyncMock(return_value=installed_extension),
        )
        update_mock = mocker.patch(
            "lnbits.core.services.extensions."
            "update_installed_extension_wasm_runtime_limits",
            mocker.AsyncMock(),
        )

        saved_limits = await extension_services.update_wasm_extension_runtime_limits(
            ext_id,
            {
                "wasm_runtime_max_execution_ms": "15000",
                "wasm_runtime_max_fuel": 0,
                "wasm_runtime_max_memory_bytes": "",
            },
        )
    finally:
        settings.lnbits_extensions_path = original_extensions_path

    assert saved_limits == {
        "wasm_runtime_max_execution_ms": 15000,
        "wasm_runtime_max_fuel": 0,
    }
    update_mock.assert_awaited_once_with(ext_id=ext_id, limits=saved_limits)


@pytest.mark.anyio
async def test_wasm_invocation_concurrency_limits(mocker: MockerFixture):
    _reset_wasm_invocation_state()
    mocker.patch(
        "lnbits.core.services.extensions.create_wasm_invocation",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.update_wasm_invocation",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.get_wasm_invocation",
        mocker.AsyncMock(return_value=None),
    )
    mocker.patch(
        "lnbits.core.services.extensions.mark_stale_wasm_invocations",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.delete_old_wasm_invocations",
        mocker.AsyncMock(),
    )
    limits = extension_services.wasm_runtime_limit_defaults()
    limits.update(
        {
            "wasm_runtime_max_concurrent_invocations": 1,
            "wasm_runtime_max_concurrent_invocations_per_extension": 1,
            "wasm_runtime_max_concurrent_invocations_per_user": 1,
        }
    )

    invocation = await start_wasm_invocation(
        extension_id="demoext",
        export_name="render",
        user_id="user-id",
        runtime_limits=limits,
    )

    with pytest.raises(ValueError, match="too many active invocations"):
        await start_wasm_invocation(
            extension_id="demoext",
            export_name="render",
            user_id="user-id",
            runtime_limits=limits,
        )

    await finish_wasm_invocation(invocation.id, status="completed")


@pytest.mark.anyio
async def test_wasm_invocation_host_call_limits(mocker: MockerFixture):
    _reset_wasm_invocation_state()
    mocker.patch(
        "lnbits.core.services.extensions.create_wasm_invocation",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.update_wasm_invocation",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.get_wasm_invocation",
        mocker.AsyncMock(return_value=None),
    )
    mocker.patch(
        "lnbits.core.services.extensions.mark_stale_wasm_invocations",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.core.services.extensions.delete_old_wasm_invocations",
        mocker.AsyncMock(),
    )
    limits = extension_services.wasm_runtime_limit_defaults()
    limits["wasm_runtime_max_host_calls"] = 1

    invocation = await start_wasm_invocation(
        extension_id="demoext",
        export_name="render",
        runtime_limits=limits,
    )
    record_wasm_invocation_host_call(invocation.id, "http.request")

    with pytest.raises(ValueError, match="host call limit"):
        record_wasm_invocation_host_call(invocation.id, "storage.get")

    await finish_wasm_invocation(invocation.id, status="failed")


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
    ext_one = make_installable_extension(ext_id_one)
    ext_two = make_installable_extension(ext_id_two)
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

        assert (
            await get_valid_extension(ext_id_one, include_deactivated=True) is not None
        )

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
