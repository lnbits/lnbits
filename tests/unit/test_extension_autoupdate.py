import asyncio
import importlib
import json
import sys
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lnbits.app import register_new_ext_routes
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
    monkeypatch.setattr(settings, "lnbits_autoupdate_extensions_interval_hours", 24)
    monkeypatch.setattr(settings, "lnbits_extensions_deactivate_all", False)
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
                archive.writestr(
                    f"{ext.id}/__init__.py",
                    "from fastapi import APIRouter\n"
                    "VERSION = '2.0.0'\n"
                    f"{ext.id}_ext = APIRouter(prefix='/{ext.id}')\n"
                    f"@{ext.id}_ext.get('/version')\n"
                    "async def version():\n"
                    "    return VERSION\n",
                )

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
    stop = mocker.patch.object(services, "stop_extension_background_work")
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
        stop=stop,
    )
    sys.modules.pop(ext.module_name, None)


@pytest.mark.parametrize("interval", [0, 1, 24])
def test_autoupdate_interval_defaults_daily_and_loads_from_env(monkeypatch, interval):
    assert ExtensionsSettings().lnbits_autoupdate_extensions_interval_hours == 24
    monkeypatch.setenv("LNBITS_AUTOUPDATE_EXTENSIONS_INTERVAL_HOURS", str(interval))
    loaded = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert loaded.lnbits_autoupdate_extensions_interval_hours == interval
    assert (
        "lnbits_autoupdate_extensions_interval_hours" in EditableSettings.model_fields
    )


@pytest.mark.parametrize("interval", [-1, 1.5])
def test_autoupdate_interval_rejects_negative_and_fractional_values(interval):
    with pytest.raises(ValueError):
        EditableSettings(lnbits_autoupdate_extensions_interval_hours=interval)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "disable_all,reload_active", [(True, False), (True, True), (False, True)]
)
async def test_autoupdate_disabled_does_not_fetch(
    update_context, settings, disable_all, reload_active
):
    settings.lnbits_autoupdate_extensions_interval_hours = 24 if disable_all else 0
    settings.lnbits_extensions_deactivate_all = disable_all
    await services.auto_update_extensions(reload_active=reload_active)
    update_context.releases.assert_not_awaited()
    update_context.download.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("active", [True, False])
@pytest.mark.parametrize("interval", [0, 24])
async def test_autoupdate_latest_compatible_preserves_state_and_paid_access(
    update_context, settings, monkeypatch, active, interval
):
    ctx = update_context
    settings.lnbits_autoupdate_extensions_interval_hours = interval
    ctx.ext.active = active
    ctx.ext.meta.installed_release.cost_sats = 100
    if active:
        ctx.ext.meta.payments = [
            ReleasePaymentInfo(
                amount=200,
                pay_link=ctx.release.pay_link,
                payment_hash="existing-payment",
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
    assert saved.meta.installed_release.cost_sats == (200 if active else 100)
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


@pytest.mark.anyio
@pytest.mark.parametrize("active", [True, False])
async def test_periodic_autoupdate_reloads_only_active_python_extensions(
    update_context, settings, mocker, monkeypatch, active
):
    ctx = update_context
    settings.lnbits_autoupdate_extensions_on_startup = False
    ctx.ext.active = active
    if not active:
        settings.lnbits_deactivated_extensions.add(ctx.ext.id)
    app = FastAPI()

    @app.get(f"/{ctx.ext.id}/version")
    async def old_version():
        return "1.0.0"

    monkeypatch.setitem(
        sys.modules, ctx.ext.module_name, SimpleNamespace(VERSION="1.0.0")
    )

    async def stop(ext_id):
        assert ext_id == ctx.ext.id
        assert sys.modules[ctx.ext.module_name].VERSION == "1.0.0"
        assert ctx.ext.id in settings.lnbits_deactivated_extensions

    ctx.stop.side_effect = stop
    mocker.patch.object(
        services.core_app_extra,
        "register_new_ext_routes",
        side_effect=register_new_ext_routes(app),
    )
    start = mocker.patch.object(services, "start_extension_background_work")

    await services.auto_update_extensions(reload_active=True)

    assert ctx.save.await_args.args[0].active is active
    if active:
        ctx.stop.assert_awaited_once_with(ctx.ext.id)
        start.assert_awaited_once_with(ctx.ext.id)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/{ctx.ext.id}/version")
        assert response.json() == "2.0.0"
        assert ctx.ext.id not in settings.lnbits_deactivated_extensions
    else:
        ctx.stop.assert_not_awaited()
        start.assert_not_awaited()
        assert ctx.ext.id in settings.lnbits_deactivated_extensions


@pytest.mark.anyio
async def test_periodic_autoupdate_reloads_wasm_routes_and_schedules(
    update_context, mocker
):
    ctx = update_context
    ctx.config.update(extension_type="wasm", wasm={"module": "extension.wasm"})
    register = mocker.patch.object(
        services.core_app_extra, "register_new_wasm_ext_routes"
    )
    schedules = mocker.patch.object(services, "ensure_wasm_extension_schedules")

    await services.auto_update_extensions(reload_active=True)

    register.assert_called_once_with(ctx.ext.id)
    schedules.assert_awaited_once_with(ctx.ext.id)
    ctx.stop.assert_awaited_once_with(ctx.ext.id)


@pytest.mark.anyio
async def test_periodic_autoupdate_activation_failure_leaves_extension_disabled(
    update_context, settings, mocker
):
    ctx = update_context
    mocker.patch.object(
        services, "activate_extension", side_effect=ValueError("Cannot load routes")
    )

    await services.auto_update_extensions(reload_active=True)

    ctx.save.assert_awaited_once()
    assert ctx.deactivate.await_args.kwargs == {"ext_id": ctx.ext.id, "active": False}
    assert ctx.ext.id in settings.lnbits_deactivated_extensions
    # Installation committed the new version before activation failed.
    assert ctx.ext.load_archive_config()["version"] == ctx.release.version


@pytest.mark.anyio
async def test_periodic_autoupdate_preserves_deactivation_during_download(
    update_context, settings, mocker
):
    ctx = update_context
    download = ctx.download.side_effect

    def deactivate_during_download(url, path):
        download(url, path)
        ctx.ext.active = False
        settings.lnbits_deactivated_extensions.add(ctx.ext.id)

    ctx.download.side_effect = deactivate_during_download
    activate = mocker.patch.object(services, "activate_extension")

    await services.auto_update_extensions(reload_active=True)

    assert ctx.save.await_args.args[0].active is False
    activate.assert_not_awaited()
    assert ctx.ext.id in settings.lnbits_deactivated_extensions


@pytest.mark.anyio
async def test_periodic_autoupdate_preserves_permissions_revoked_during_download(
    update_context,
):
    ctx = update_context
    permission = ExtensionPermission(id="wallet.read")
    ctx.ext.permissions = [permission]
    ctx.config.update(
        extension_type="wasm",
        wasm={"module": "extension.wasm"},
        permissions=[permission.model_dump()],
    )
    download = ctx.download.side_effect

    def revoke_during_download(url, path):
        download(url, path)
        ctx.ext.permissions = []

    ctx.download.side_effect = revoke_during_download

    await services.auto_update_extensions(reload_active=True)

    ctx.save.assert_not_awaited()
    ctx.stop.assert_not_awaited()
    assert ctx.ext.zip_path.read_bytes() == b"cached installed release"


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["download", "migration"])
async def test_autoupdate_cancellation_preserves_cached_archive(
    update_context, settings, mocker, phase
):
    ctx = update_context
    if phase == "download":
        mocker.patch.object(
            InstallableExtension, "download_archive", side_effect=asyncio.CancelledError
        )
    else:
        ctx.migrate.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await services.auto_update_extensions(reload_active=True)

    assert ctx.ext.zip_path.read_bytes() == b"cached installed release"
    ctx.save.assert_not_awaited()
    if phase == "migration":
        assert ctx.ext.id in settings.lnbits_deactivated_extensions
    else:
        ctx.deactivate.assert_not_awaited()
