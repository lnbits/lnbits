from pathlib import Path
from uuid import uuid4

import pytest

from lnbits.core.crud.extensions import create_user_extension, get_user_extension
from lnbits.core.crud.users import get_account
from lnbits.core.models.extensions import (
    Extension,
    ExtensionMeta,
    ExtensionRelease,
    UserExtension,
)
from lnbits.core.models.extensions_builder import (
    ActionFields,
    ClientDataFields,
    DataField,
    DataFields,
    ExtensionData,
    OwnerDataFields,
    PublicPageFields,
    SettingsFields,
)
from lnbits.core.models.users import AccountId
from lnbits.core.views.extensions_builder_api import (
    api_build_extension,
    api_delete_extension_builder_data,
    api_deploy_extension,
    api_preview_extension,
)
from lnbits.settings import Settings


def _extension_data(ext_id: str = "demoext") -> ExtensionData:
    return ExtensionData(
        id=ext_id,
        name="Demo Extension",
        stub_version="0.1.0",
        short_description="Generated extension",
        owner_data=DataFields(
            name="OwnerData",
            fields=[DataField(name="wallet_id", type="wallet")],
        ),
        client_data=DataFields(
            name="ClientData",
            fields=[DataField(name="amount", type="int")],
        ),
        settings_data=SettingsFields(name="SettingsData", fields=[]),
        public_page=PublicPageFields(
            owner_data_fields=OwnerDataFields(),
            client_data_fields=ClientDataFields(),
            action_fields=ActionFields(),
        ),
    )


def _release(ext_id: str) -> ExtensionRelease:
    return ExtensionRelease(
        name=ext_id,
        version="0.1.0",
        archive=f"https://example.com/{ext_id}.zip",
        source_repo="org/repo",
        is_github_release=False,
        hash=f"hash-{ext_id}",
        icon=f"/{ext_id}/static/image/{ext_id}.png",
    )


@pytest.mark.anyio
async def test_extensions_builder_api_build_preview_and_cleanup(
    tmp_path, settings: Settings, mocker, from_user
):
    ext_id = f"builder_{uuid4().hex[:8]}"
    data = _extension_data(ext_id)
    build_dir = tmp_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "index.txt").write_text("hello")

    original_data_folder = settings.lnbits_data_folder
    build_mock = mocker.patch(
        "lnbits.core.views.extensions_builder_api.build_extension_from_data",
        mocker.AsyncMock(return_value=(_release(ext_id), build_dir)),
    )
    clean_mock = mocker.patch("lnbits.core.views.extensions_builder_api.clean_extension_builder_data")

    try:
        settings.lnbits_data_folder = str(tmp_path)

        build_response = await api_build_extension(data)
        assert Path(build_response.path).is_file()
        assert build_response.filename == f"{ext_id}.zip"

        preview = await api_preview_extension(data, AccountId(id=from_user.id))
        assert preview.success is True
        assert ext_id in preview.message

        cleaned = await api_delete_extension_builder_data()
        assert cleaned.success is True
        clean_mock.assert_called_once()
        assert build_mock.await_count == 2
    finally:
        settings.lnbits_data_folder = original_data_folder


@pytest.mark.anyio
async def test_extensions_builder_api_deploy_updates_user_extension(
    tmp_path, settings: Settings, mocker, admin_user
):
    ext_id = f"deploy_{uuid4().hex[:8]}"
    data = _extension_data(ext_id)
    account = await get_account(admin_user.id)
    assert account is not None

    build_root = tmp_path / "deploy-root" / ext_id
    build_root.mkdir(parents=True, exist_ok=True)
    (build_root / "manifest.json").write_text("{}")

    original_data_folder = settings.lnbits_data_folder
    await create_user_extension(
        UserExtension(user=account.id, extension=ext_id, active=False)
    )

    mocker.patch(
        "lnbits.core.views.extensions_builder_api.build_extension_from_data",
        mocker.AsyncMock(return_value=(_release(ext_id), build_root)),
    )
    install_mock = mocker.patch(
        "lnbits.core.views.extensions_builder_api.install_extension",
        mocker.AsyncMock(return_value=Extension(code=ext_id, is_valid=True)),
    )
    activate_mock = mocker.patch(
        "lnbits.core.views.extensions_builder_api.activate_extension",
        mocker.AsyncMock(),
    )

    try:
        settings.lnbits_data_folder = str(tmp_path)
        deployed = await api_deploy_extension(data, account=account)
    finally:
        settings.lnbits_data_folder = original_data_folder

    assert deployed.success is True
    assert ext_id in deployed.message
    install_mock.assert_awaited_once()
    activate_mock.assert_awaited_once()

    user_ext = await get_user_extension(account.id, ext_id)
    assert user_ext is not None
    assert user_ext.active is True
