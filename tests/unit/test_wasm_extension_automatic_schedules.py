import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture

from lnbits import app as app_module
from lnbits.core.crud import scheduler as schedule_crud
from lnbits.core.migrations import m054_create_scheduled_jobs
from lnbits.core.models.extensions import Extension, ExtensionPermission
from lnbits.core.services import extensions as extension_service
from lnbits.core.services import scheduler as scheduler_service
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.wasm import scheduler as wasm_scheduler
from lnbits.core.wasm_ext.wasm.config import parse_wasm_extension_config
from lnbits.db import DB_TYPE, SQLITE, Database
from lnbits.helpers import sha256s
from lnbits.settings import Settings
from tests.helpers import make_installable_extension


def automatic_config() -> dict:
    policy = {
        "handler": "collect",
        "cron_expression": "* * * * *",
        "timezone": "UTC",
    }
    return {
        "id": "demo",
        "name": "Demo",
        "short_description": "Demo",
        "version": "0.1.0",
        "extension_type": "wasm",
        "wasm": {
            "module": "module.wasm",
            "exports": [{"name": "collect", "visibility": "event"}],
        },
        "schedules": [policy],
        "permissions": [{"id": "scheduler.extension", "policies": [policy]}],
    }


@pytest.mark.parametrize("invalid", ["duplicate", "missing", "public", "cron"])
def test_automatic_schedule_rejects_invalid_declarations(invalid):
    config = automatic_config()
    if invalid == "duplicate":
        config["schedules"] *= 2
    elif invalid == "missing":
        config["wasm"]["exports"] = []
    elif invalid == "public":
        config["wasm"]["exports"][0]["visibility"] = "public"
    else:
        config["schedules"][0]["cron_expression"] = "* * * * * *"
    with pytest.raises(ValueError):
        parse_wasm_extension_config("demo", config)


def test_automatic_schedule_requires_matching_requested_and_granted_policy():
    config = automatic_config()
    extension = make_installable_extension("demo")
    grants = [ExtensionPermission.parse_obj(p) for p in config["permissions"]]
    assert validate_wasm_extension_permissions(extension, grants, config) == grants
    with pytest.raises(ValueError, match="requires permission approval"):
        validate_wasm_extension_permissions(extension, None, config)
    with pytest.raises(ValueError, match="matching scheduler.extension"):
        validate_wasm_extension_permissions(extension, [], config)
    # A user policy cannot authorize an automatic instance job.
    config["permissions"][0]["id"] = "scheduler.user"
    with pytest.raises(ValueError, match="matching scheduler.extension"):
        validate_wasm_extension_permissions(extension, [], config)
    config["permissions"] = []
    with pytest.raises(ValueError, match="matching scheduler.extension"):
        validate_wasm_extension_permissions(extension, [], config)


def test_automatic_schedule_cannot_exceed_approved_cadence():
    config = automatic_config()
    grants = [
        ExtensionPermission(
            id="scheduler.extension",
            policies=[{"handler": "collect", "cron_expression": "*/5 * * * *"}],
        )
    ]
    with pytest.raises(ValueError):
        validate_wasm_extension_permissions(
            make_installable_extension("demo"), grants, config
        )


@pytest.fixture
async def automatic_extension(
    tmp_path: Path, settings: Settings, mocker: MockerFixture
):
    if DB_TYPE != SQLITE:
        pytest.skip("Isolated scheduler database tests require SQLite.")
    settings.lnbits_data_folder = str(tmp_path)
    settings.lnbits_extensions_deactivate_all = False
    database = Database("automatic_schedule_test")
    async with database.connect() as conn:
        await m054_create_scheduled_jobs(conn)
    mocker.patch.object(schedule_crud, "db", database)
    config = parse_wasm_extension_config("demo", automatic_config())
    extension = SimpleNamespace(config=config, exports=config.wasm.exports)
    installed = SimpleNamespace(
        active=True, is_wasm=True, permissions=config.permissions
    )
    mocker.patch.object(
        wasm_scheduler.core_app_extra.wasm_extension_registry,
        "get",
        return_value=extension,
    )
    mocker.patch.object(
        scheduler_service,
        "get_installed_extension",
        mocker.AsyncMock(return_value=installed),
    )
    scheduler = scheduler_service.Scheduler()
    scheduler.register(
        "extension:demo", "collect", wasm_scheduler.dispatch_wasm_schedule
    )
    mocker.patch.object(wasm_scheduler, "scheduler", scheduler)
    yield SimpleNamespace(
        extension=extension, installed=installed, db=database, scheduler=scheduler
    )
    await database.engine.dispose()


@pytest.mark.anyio
async def test_automatic_schedule_creation_is_idempotent_and_preserves_pause_and_lease(
    automatic_extension,
):
    await wasm_scheduler.ensure_wasm_extension_schedules("demo")
    jobs = await automatic_extension.scheduler.list("extension:demo")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == sha256s(json.dumps(["demo", None, "collect"]))
    assert job.user_id is None and job.enabled and job.next_run_at
    await wasm_scheduler.ensure_wasm_extension_schedules("demo")
    assert await automatic_extension.scheduler.list("extension:demo") == jobs

    await automatic_extension.db.execute(
        """UPDATE scheduled_jobs SET enabled = false,
           lease_token = 'active-lease', lease_until = 2000000000 WHERE id = :id""",
        {"id": job.id},
    )
    paused = await schedule_crud.get_scheduled_job(job.id)
    await wasm_scheduler.ensure_wasm_extension_schedules("demo")
    assert await schedule_crud.get_scheduled_job(job.id) == paused


@pytest.mark.anyio
async def test_automatic_schedule_updates_approved_cadence_without_enabling_paused_job(
    automatic_extension,
):
    await wasm_scheduler.ensure_wasm_extension_schedules("demo")
    job = (await automatic_extension.scheduler.list("extension:demo"))[0]
    await automatic_extension.db.execute(
        "UPDATE scheduled_jobs SET enabled = false WHERE id = :id", {"id": job.id}
    )
    automatic_extension.extension.config.schedules[0].cron_expression = "*/5 * * * *"
    automatic_extension.installed.permissions[0].policies[0][
        "cron_expression"
    ] = "*/5 * * * *"
    await wasm_scheduler.ensure_wasm_extension_schedules("demo")
    updated = await schedule_crud.get_scheduled_job(job.id)
    assert updated and updated.cron_expression == "*/5 * * * *"
    assert not updated.enabled


@pytest.mark.anyio
@pytest.mark.parametrize("denied", ["revoked", "inactive", "all_disabled"])
async def test_automatic_schedule_rechecks_access_even_for_existing_job(
    automatic_extension, settings: Settings, denied
):
    await wasm_scheduler.ensure_wasm_extension_schedules("demo")
    jobs = await automatic_extension.scheduler.list("extension:demo")
    if denied == "revoked":
        automatic_extension.installed.permissions = []
    elif denied == "inactive":
        automatic_extension.installed.active = False
    else:
        settings.lnbits_extensions_deactivate_all = True
    with pytest.raises(PermissionError):
        await wasm_scheduler.ensure_wasm_extension_schedules("demo")
    assert await automatic_extension.scheduler.list("extension:demo") == jobs


@pytest.mark.anyio
async def test_automatic_schedule_is_created_on_activation_and_restored_at_startup(
    automatic_extension, mocker: MockerFixture
):
    extension = Extension(code="demo", is_valid=True, is_wasm=True)
    automatic_extension.installed.active = False

    async def set_active(*, ext_id, active):
        assert ext_id == "demo"
        automatic_extension.installed.active = active

    mocker.patch.object(
        extension_service.core_app_extra, "register_new_wasm_ext_routes"
    )
    mocker.patch.object(
        extension_service, "update_installed_extension_state", side_effect=set_active
    )
    await extension_service.activate_extension(extension)
    jobs = await automatic_extension.scheduler.list("extension:demo")
    assert len(jobs) == 1 and jobs[0].user_id is None

    mocker.patch.object(app_module, "check_installed_extensions", mocker.AsyncMock())
    mocker.patch.object(
        app_module, "get_valid_extensions", mocker.AsyncMock(return_value=[extension])
    )
    mocker.patch.object(app_module, "is_wasm_extension_id", return_value=True)
    mocker.patch.object(app_module, "register_wasm_extension")
    failure = mocker.patch.object(
        app_module, "update_installed_extension_state", mocker.AsyncMock()
    )
    await app_module.check_and_register_extensions(FastAPI())
    assert await automatic_extension.scheduler.list("extension:demo") == jobs
    # A missing job is restored on startup without a user visiting the UI.
    await automatic_extension.scheduler.delete("extension:demo", jobs[0].id)
    await app_module.check_and_register_extensions(FastAPI())
    restored = await automatic_extension.scheduler.list("extension:demo")
    assert len(restored) == 1 and restored[0].id == jobs[0].id
    failure.assert_not_awaited()


@pytest.mark.anyio
async def test_automatic_schedule_activation_failure_does_not_leave_extension_active(
    mocker: MockerFixture,
):
    mocker.patch.object(
        extension_service.core_app_extra, "register_new_wasm_ext_routes"
    )
    update = mocker.patch.object(
        extension_service, "update_installed_extension_state", mocker.AsyncMock()
    )
    stop = mocker.patch.object(
        extension_service.scheduler, "stop_namespace", mocker.AsyncMock()
    )
    mocker.patch.object(
        wasm_scheduler,
        "ensure_wasm_extension_schedules",
        mocker.AsyncMock(side_effect=PermissionError("Schedule permission revoked.")),
    )
    with pytest.raises(PermissionError, match="revoked"):
        await extension_service.activate_extension(
            Extension(code="demo", is_valid=True, is_wasm=True)
        )
    assert [call.kwargs["active"] for call in update.await_args_list] == [True, False]
    stop.assert_awaited_once_with("extension:demo")
