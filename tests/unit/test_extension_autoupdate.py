import importlib
import json
import sys
import zipfile
from types import SimpleNamespace

import pytest

from lnbits.core.models.extensions import (
    ExtensionPermission,
    InstallableExtension,
    ReleasePaymentInfo,
)
from lnbits.core.services import extensions as services
from lnbits.settings import EditableSettings, ExtensionsSettings, Settings
from tests.helpers import make_extension_release, make_installable_extension


@pytest.fixture
def update_context(tmp_path, settings, monkeypatch, mocker):
    monkeypatch.setattr(settings, "lnbits_data_folder", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "lnbits_extensions_path", str(tmp_path / "code"))
    monkeypatch.setattr(settings, "lnbits_wasm_extensions_path", str(tmp_path / "wasm"))
    monkeypatch.setattr(settings, "lnbits_autoupdate_extensions", True)
    monkeypatch.setattr(settings, "lnbits_running", True)
    monkeypatch.setattr(settings, "lnbits_deactivated_extensions", set())
    monkeypatch.syspath_prepend(str(tmp_path / "code" / "extensions"))
    ext = make_installable_extension("autoupdate_demo")
    assert ext.meta and ext.meta.installed_release
    ext.meta.installed_release.payment_hash = "existing-payment"
    release = make_extension_release(ext.id, "2.0.0")
    release.hash = None
    config = {
        "id": ext.id,
        "name": ext.name,
        "version": release.version,
        "short_description": "Updated extension",
    }
    ext.zip_path.write_bytes(b"cached installed release")

    def download(_url, path):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"{ext.id}/config.json", json.dumps(config))
            if config.get("extension_type") == "wasm":
                archive.writestr(f"{ext.id}/extension.wasm", b"module")
            else:
                archive.writestr(f"{ext.id}/__init__.py", "VERSION = '2.0.0'\n")

    download_mock = mocker.patch(
        "lnbits.core.models.extensions.download_url", side_effect=download
    )
    releases_mock = mocker.patch.object(
        InstallableExtension, "get_extension_releases", return_value=[release]
    )
    mocker.patch.object(services, "get_installed_extensions", return_value=[ext])
    mocker.patch.object(services, "get_installed_extension", return_value=ext)
    mocker.patch.object(services, "get_db_version", return_value=None)
    migrate = mocker.patch.object(services, "migrate_extension_database")
    save = mocker.patch.object(services, "update_installed_extension")
    deactivate = mocker.patch.object(services, "update_installed_extension_state")
    mocker.patch.object(services, "stop_extension_background_work")
    mocker.patch.object(services, "load_wasm_extension")
    mocker.patch.object(services, "warm_wasm_extension")
    yield SimpleNamespace(
        ext=ext,
        release=release,
        config=config,
        releases=releases_mock,
        download=download_mock,
        migrate=migrate,
        save=save,
        deactivate=deactivate,
    )
    sys.modules.pop(ext.module_name, None)


def test_autoupdate_setting_defaults_on_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv("LNBITS_AUTOUPDATE_EXTENSIONS", raising=False)
    assert ExtensionsSettings().lnbits_autoupdate_extensions is True
    monkeypatch.setenv("LNBITS_AUTOUPDATE_EXTENSIONS", "false")
    loaded = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert loaded.lnbits_autoupdate_extensions is False
    assert "lnbits_autoupdate_extensions" in EditableSettings.model_fields


@pytest.mark.anyio
async def test_autoupdate_disabled_does_not_fetch(update_context, settings):
    settings.lnbits_autoupdate_extensions = False
    await services.auto_update_extensions()
    update_context.releases.assert_not_awaited()
    update_context.download.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("active", [True, False])
async def test_autoupdate_latest_compatible_preserves_state_and_paid_access(
    update_context, settings, monkeypatch, active
):
    ctx = update_context
    ctx.ext.active = active
    if active:
        ctx.ext.meta.payments = [
            ReleasePaymentInfo(
                pay_link=ctx.release.pay_link, payment_hash="existing-payment"
            )
        ]
    if not active:
        settings.lnbits_deactivated_extensions.add(ctx.ext.id)
    ctx.releases.return_value = [
        ctx.release.model_copy(update={"version": "1.5.0"}),
        ctx.release,
        ctx.release.model_copy(
            update={"version": "3.0.0", "is_version_compatible": False}
        ),
        ctx.release.model_copy(update={"version": "4.0.0rc1"}),
        ctx.release.model_copy(update={"version": "invalid"}),
        ctx.release.model_copy(
            update={"version": "5.0.0", "source_repo": "other/repo"}
        ),
    ]
    monkeypatch.setitem(
        sys.modules, ctx.ext.module_name, SimpleNamespace(VERSION="1.0.0")
    )

    async def migrate(ext, _version):
        assert importlib.import_module(ext.module_name).VERSION == "2.0.0"

    ctx.migrate.side_effect = migrate
    await services.auto_update_extensions()

    saved = ctx.save.await_args.args[0]
    assert saved.version == "2.0.0"
    assert saved.active is active
    assert (ctx.ext.id in settings.lnbits_deactivated_extensions) is (not active)
    assert "payment_hash=existing-payment" in ctx.download.call_args.args[0]
    assert saved.meta.installed_release.payment_hash == "existing-payment"
    assert saved.meta.payments == ctx.ext.meta.payments
    assert ctx.ext.installed_version == "1.0.0"
    ctx.deactivate.assert_not_awaited()
    assert zipfile.is_zipfile(ctx.ext.zip_path)


@pytest.mark.anyio
@pytest.mark.parametrize("version", ["0.5.0", "1.0.0", "2.0.0rc1", "2.0.0.dev1"])
async def test_autoupdate_does_not_downgrade_reinstall_or_install_prereleases(
    update_context, version
):
    update_context.release.version = version
    await services.auto_update_extensions()
    update_context.download.assert_not_called()
    update_context.save.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["download", "compatibility", "hash", "migration"])
async def test_autoupdate_failure_preserves_archive_and_continues(
    update_context, settings, mocker, failure
):
    ctx = update_context
    if failure == "download":
        ctx.download.side_effect = OSError("Offline")
    elif failure == "compatibility":
        ctx.config["min_lnbits_version"] = "9999.0.0"
    elif failure == "hash":
        ctx.release.hash = "incorrect-hash"
    else:
        ctx.migrate.side_effect = ValueError("Migration failed")
    second = make_installable_extension("another_extension")
    mocker.patch.object(
        services, "get_installed_extensions", return_value=[ctx.ext, second]
    )
    ctx.releases.side_effect = [[ctx.release], []]

    await services.auto_update_extensions()

    assert ctx.ext.zip_path.read_bytes() == b"cached installed release"
    ctx.save.assert_not_awaited()
    assert ctx.releases.await_count == 2
    if failure == "migration":
        ctx.deactivate.assert_awaited_once_with(ext_id=ctx.ext.id, active=False)
        assert ctx.ext.id in settings.lnbits_deactivated_extensions
    else:
        ctx.deactivate.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("permission_change", ["unchanged", "new", "broader"])
async def test_autoupdate_wasm_requires_approval_for_permission_changes(
    update_context, permission_change
):
    ctx = update_context
    permission = ExtensionPermission(
        id="http.request", policies=[{"host": "https://api.example.com"}]
    )
    ctx.ext.permissions = [permission]
    ctx.config.update(
        extension_type="wasm",
        wasm={"module": "extension.wasm"},
        permissions=[permission.model_dump()],
    )
    if permission_change == "new":
        ctx.config["permissions"].append({"id": "wallet.read"})
    elif permission_change == "broader":
        ctx.config["permissions"][0]["policies"].append({"host": "https://new.example"})

    await services.auto_update_extensions()

    if permission_change == "unchanged":
        ctx.save.assert_awaited_once()
        assert ctx.save.await_args.args[0].permissions == [permission]
        assert (ctx.ext.wasm_ext_dir / "extension.wasm").is_file()
    else:
        ctx.save.assert_not_awaited()
        ctx.migrate.assert_not_awaited()
        assert not ctx.ext.wasm_ext_dir.exists()
        assert ctx.ext.zip_path.read_bytes() == b"cached installed release"
    ctx.deactivate.assert_not_awaited()


@pytest.mark.anyio
async def test_autoupdate_shutdown_during_download_does_not_install(
    update_context, settings
):
    ctx = update_context
    download = ctx.download.side_effect

    def stop_after_download(url, path):
        download(url, path)
        settings.lnbits_running = False

    ctx.download.side_effect = stop_after_download
    await services.auto_update_extensions()
    ctx.save.assert_not_awaited()
    ctx.deactivate.assert_not_awaited()
    assert ctx.ext.zip_path.read_bytes() == b"cached installed release"
