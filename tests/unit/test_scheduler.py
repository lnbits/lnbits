import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture
from wasmtime import Trap

from lnbits.app import shutdown
from lnbits.core.crud import extensions as extension_crud
from lnbits.core.crud import scheduler as crud
from lnbits.core.crud import users as user_crud
from lnbits.core.migrations import (
    m001_initial,
    m020_add_column_column_to_user_extensions,
    m044_add_activated_to_accounts,
    m049_add_permissions_to_user_extensions,
    m054_create_scheduled_jobs,
    m055_create_scheduled_job_runs,
)
from lnbits.core.models.extensions import Extension, ExtensionPermission, UserExtension
from lnbits.core.models.scheduler import (
    ScheduleConfig,
    ScheduledJob,
    ScheduledJobRunFilters,
    ScheduledJobRunStatus,
)
from lnbits.core.models.users import AccountId
from lnbits.core.services import scheduler as service
from lnbits.core.services.scheduler import Scheduler, check_schedule_access
from lnbits.core.views import extension_api
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.scheduler import ExtensionSchedulerAPI, ScheduleSetRequest
from lnbits.db import DB_TYPE, SQLITE, Database, Filters
from lnbits.settings import SchedulerSettings, Settings
from lnbits.utils.cron import next_run_at

NOW = 1735689600  # 2025-01-01 00:00 UTC


@pytest.fixture
async def schedule_db(tmp_path: Path, settings: Settings, mocker: MockerFixture):
    if DB_TYPE != SQLITE:
        pytest.skip("Isolated scheduler database tests require SQLite.")
    settings.lnbits_data_folder = str(tmp_path)
    database = Database("scheduler_test")
    async with database.connect() as conn:
        await m054_create_scheduled_jobs(conn)
        await m055_create_scheduled_job_runs(conn)
    mocker.patch.object(crud, "db", database)
    yield database
    await database.engine.dispose()


@pytest.fixture
def clock(mocker: MockerFixture):
    clock = SimpleNamespace(now=NOW)
    mocker.patch.object(service, "time", SimpleNamespace(time=lambda: clock.now))
    return clock


@pytest.fixture(params=["python", "wasm"])
async def extension_job_scopes(
    schedule_db: Database,
    settings: Settings,
    mocker: MockerFixture,
    request: pytest.FixtureRequest,
):
    settings.lnbits_extensions_deactivate_all = False
    async with schedule_db.connect() as conn:
        await m001_initial(conn)
        await m020_add_column_column_to_user_extensions(conn)
        await m049_add_permissions_to_user_extensions(conn)
    mocker.patch.object(extension_crud, "db", schedule_db)
    for user_id, extension_id in [("alice", "one"), ("bob", "one"), ("alice", "two")]:
        await extension_crud.create_user_extension(
            UserExtension(user=user_id, extension=extension_id, active=True)
        )
    installed = SimpleNamespace(
        active=True,
        is_wasm=request.param == "wasm",
        requires_payment=False,
        permissions=[
            ExtensionPermission(
                id=permission,
                policies=[{"handler": "check", "cron_expression": "* * * * *"}],
            )
            for permission in ("scheduler.user", "scheduler.extension")
        ],
    )
    for module in (service, extension_api):
        mocker.patch.object(
            module, "get_installed_extension", mocker.AsyncMock(return_value=installed)
        )
    mocker.patch.object(
        extension_api,
        "get_valid_extensions",
        mocker.AsyncMock(
            return_value=[
                Extension(code=code, is_valid=True) for code in ("one", "two")
            ]
        ),
    )
    mocker.patch.object(
        service,
        "get_account",
        mocker.AsyncMock(return_value=SimpleNamespace(activated=True)),
    )
    return {
        "alice:first": ("extension:one", "alice"),
        "alice:second": ("extension:one", "alice"),
        "bob": ("extension:one", "bob"),
        "shared": ("extension:one", None),
        "alice:other-extension": ("extension:two", "alice"),
    }


@pytest.fixture
def wasm_schedule_grants(settings: Settings, mocker: MockerFixture):
    settings.lnbits_extensions_deactivate_all = False
    extension = SimpleNamespace(
        active=True,
        is_wasm=True,
        permissions=[
            ExtensionPermission(
                id="scheduler.user",
                policies=[{"handler": "check", "cron_expression": "*/10 * * * *"}],
            ),
            ExtensionPermission(
                id="scheduler.extension",
                policies=[{"handler": "check", "cron_expression": "*/20 * * * *"}],
            ),
        ],
    )
    mocker.patch.object(
        service, "get_installed_extension", mocker.AsyncMock(return_value=extension)
    )
    mocker.patch.object(
        service,
        "get_account",
        mocker.AsyncMock(return_value=SimpleNamespace(activated=True)),
    )
    mocker.patch.object(
        service,
        "get_user_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(active=True)),
    )
    return extension


def job(job_id: str = "test", **kwargs) -> ScheduledJob:
    return ScheduledJob(
        id=job_id,
        handler="check",
        cron_expression="* * * * *",
        namespace="core",
        next_run_at=NOW - 600,
        **kwargs,
    )


def stamp(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp())


@pytest.mark.parametrize(
    "expression",
    [
        "* * * * * *",
        "0 * * * * ? *",
        "@daily",
        "0 0 L * *",
        "0 0 15W * *",
        "0 0 * * MON#2",
        "H * * * *",
        "? * * * *",
        "61 * * * *",
        "*/0 * * * *",
        "0 0 * JANJAN *",
    ],
)
def test_rejects_unsupported_or_invalid_cron(expression: str):
    with pytest.raises(ValidationError):
        ScheduleConfig(handler="check", cron_expression=expression)


@pytest.mark.parametrize(
    ("expression", "after", "expected"),
    [
        ("*/10 * * * *", "2025-01-01T00:00:00+00:00", "2025-01-01T00:10:00+00:00"),
        ("0 9 ? * MON-FRI", "2025-01-03T10:00:00+00:00", "2025-01-06T09:00:00+00:00"),
        ("0 0 29 FEB *", "2025-01-01T00:00:00+00:00", "2028-02-29T00:00:00+00:00"),
        ("0 9 * * 0", "2025-01-01T00:00:00+00:00", "2025-01-05T09:00:00+00:00"),
        ("0 9 * * 7", "2025-01-01T00:00:00+00:00", "2025-01-05T09:00:00+00:00"),
        ("0 9 1 * MON", "2025-01-01T10:00:00+00:00", "2025-01-06T09:00:00+00:00"),
    ],
)
def test_next_occurrence(expression: str, after: str, expected: str):
    assert next_run_at(expression, "UTC", stamp(after)) == stamp(expected)


def test_timezone_and_dst_behavior():
    assert next_run_at("0 9 * * *", "Europe/Bucharest", NOW) == NOW + 7 * 3600
    # croniter moves a nonexistent local time to the spring transition.
    assert next_run_at(
        "30 2 * * *", "Europe/Berlin", stamp("2026-03-28T02:00:00+00:00")
    ) == stamp("2026-03-29T01:00:00+00:00")
    # A repeated local time is a distinct UTC occurrence and can run twice.
    assert next_run_at(
        "30 2 * * *", "Europe/Berlin", stamp("2026-10-25T00:30:00+00:00")
    ) == stamp("2026-10-25T01:30:00+00:00")
    assert next_run_at("0 0 31 FEB *", "UTC", NOW) is None


@pytest.mark.parametrize(
    "fields",
    [
        {"timezone": "Not/AZone"},
        {"payload_json": "[]"},
        {"payload_json": "{"},
        {"payload_json": '{"x":"' + "x" * 8192 + '"}'},
        {"user_id": "another-user"},
        {"namespace": "core"},
        {"id": "<bad>"},
    ],
)
def test_config_rejects_invalid_payloads_and_ownership(fields: dict):
    with pytest.raises(ValidationError):
        ScheduleConfig(handler="check", cron_expression="* * * * *", **fields)


@pytest.mark.anyio
async def test_persistence_and_scope_isolation(schedule_db):
    first = job().copy(update={"namespace": "extension:one", "user_id": "alice"})
    await crud.save_scheduled_job(first)
    for changes in (
        {"user_id": "bob"},
        {"user_id": None},
        {"namespace": "extension:two"},
    ):
        with pytest.raises(PermissionError):
            await crud.save_scheduled_job(first.copy(update=changes))
    page = await crud.get_scheduled_jobs_paginated("extension:one", "alice")
    assert page.data == [first]
    assert page.total == 1
    for namespace, owner in [("extension:one", None), ("extension:two", "alice")]:
        page = await crud.get_scheduled_jobs_paginated(namespace, owner)
        assert page.data == []
        assert page.total == 0
    assert not await crud.delete_scheduled_job(first.id, "extension:one", "bob", NOW)
    first.enabled = False
    await crud.save_scheduled_job(first)
    assert await crud.get_due_scheduled_jobs(NOW, 10) == []
    # A fresh connection to the same database sees the persistent record.
    connection = Database("scheduler_test")
    try:
        stored = await connection.fetchone(
            "SELECT * FROM scheduled_jobs WHERE id = :id",
            {"id": first.id},
            ScheduledJob,
        )
        assert stored.user_id == "alice"
        assert not stored.enabled
    finally:
        await connection.engine.dispose()


@pytest.mark.anyio
async def test_service_list_paginated_returns_page_and_total(schedule_db):
    for job_id in ("first", "second", "third"):
        await crud.save_scheduled_job(job(job_id))
    worker = Scheduler()
    page = await worker.list_paginated("core", limit=1, offset=1)
    assert [item.id for item in page.data] == ["second"]
    assert page.total == 3


@pytest.mark.anyio
async def test_atomic_claim_and_expired_lease_recovery(schedule_db):
    await crud.save_scheduled_job(job())
    claims = await asyncio.gather(
        crud.claim_scheduled_job("test", "one", NOW, NOW + 60),
        crud.claim_scheduled_job("test", "two", NOW, NOW + 60),
    )
    claimed = [item for item in claims if item]
    assert len(claimed) == 1
    first = claimed[0]
    assert not await crud.renew_scheduled_job("test", "wrong", NOW, NOW + 60)
    assert not await crud.delete_scheduled_job("test", "core", None, NOW)
    assert await crud.claim_scheduled_job("test", "three", NOW + 59, NOW + 120) is None
    second = await crud.claim_scheduled_job("test", "three", NOW + 60, NOW + 120)
    assert second and second.lease_token == "three"
    # The old process must not be able to release another worker's claim.
    await crud.finish_scheduled_job(first, NOW + 600)
    stored = await crud.get_scheduled_job("test")
    assert stored and stored.lease_token == "three"


@pytest.mark.anyio
async def test_restart_coalesces_missed_runs(schedule_db, clock, mocker: MockerFixture):
    await crud.save_scheduled_job(job())
    callback = mocker.AsyncMock()
    restarted = Scheduler()
    restarted.register("core", "check", callback)
    await restarted.tick()
    await asyncio.wait_for(restarted.running["test"][1], 1)
    await restarted.tick()
    callback.assert_awaited_once()
    stored = await crud.get_scheduled_job("test")
    assert stored and stored.next_run_at == NOW + 60
    assert stored.lease_token is None
    await restarted.stop()


@pytest.mark.anyio
async def test_user_schedule_limit_defaults_and_live_changes(
    schedule_db, clock, wasm_schedule_grants, mocker: MockerFixture
):
    worker = Scheduler()
    callback = mocker.AsyncMock()
    worker.register("extension:one", "check", callback)
    mocker.patch("lnbits.core.wasm_ext.api.scheduler.scheduler", worker)
    mocker.patch(
        "lnbits.core.wasm_ext.api.scheduler.get_account",
        mocker.AsyncMock(return_value=SimpleNamespace(activated=True)),
    )
    api = ExtensionSchedulerAPI(
        ExtensionHostAPI("one", ["scheduler.user"], user_id="alice")
    )
    jobs = []
    for index in range(10):
        response = await api.set(
            ScheduleSetRequest(
                handler="check", cron_expression="*/10 * * * *", enabled=index == 0
            )
        )
        jobs.append(json.loads(response.schedule_json))
    assert len({item["id"] for item in jobs}) == 10
    request = ScheduleSetRequest(handler="check", cron_expression="*/10 * * * *")
    with pytest.raises(ValueError, match="job limit"):
        await api.set(request)

    # Lowering the live grant preserves updates, pauses, and execution.
    policy = wasm_schedule_grants.permissions[0].policies[0]
    policy["max_jobs_per_user"] = 1
    response = await api.set(
        ScheduleSetRequest(
            id=jobs[0]["id"],
            handler="check",
            cron_expression="*/10 * * * *",
            payload_json='{"updated": true}',
        )
    )
    assert json.loads(response.schedule_json)["payload_json"] == '{"updated": true}'
    with pytest.raises(ValueError, match="job limit"):
        await api.set(request)
    clock.now += 600
    await worker.tick()
    await asyncio.wait_for(worker.running[jobs[0]["id"]][1], 1)
    callback.assert_awaited_once()
    await worker.stop()

    # Deletion frees slots; increasing the live limit permits new jobs immediately.
    for item in jobs[1:]:
        assert await worker.delete("extension:one", item["id"], user_id="alice")
    with pytest.raises(ValueError, match="job limit"):
        await api.set(request)
    assert await worker.delete("extension:one", jobs[0]["id"], user_id="alice")
    await api.set(request)
    policy["max_jobs_per_user"] = 2
    await api.set(ScheduleSetRequest(handler="check", cron_expression="*/10 * * * *"))
    assert (await worker.list_paginated("extension:one", user_id="alice")).total == 2


@pytest.mark.anyio
async def test_user_schedule_limit_is_scoped(
    schedule_db, clock, wasm_schedule_grants, mocker: MockerFixture
):
    worker = Scheduler()
    policies = wasm_schedule_grants.permissions[0].policies
    policies[0]["max_jobs_per_user"] = 2
    policies.append({**policies[0], "handler": "other"})
    for namespace in ("extension:one", "extension:two"):
        for handler in ("check", "other"):
            worker.register(namespace, handler, mocker.AsyncMock())

    async def create(index, namespace="extension:one", owner="alice", handler="check"):
        return await worker.save(
            namespace,
            ScheduleConfig(
                id=f"{namespace}:{owner}:{handler}:{index}",
                handler=handler,
                cron_expression="*/10 * * * *",
                enabled=False,
            ),
            user_id=owner,
        )

    existing = await create(0)
    await create(1)
    with pytest.raises(ValueError, match="job limit"):
        await create(2)
    await create(0, owner="bob")
    await create(0, namespace="extension:two")
    await create(0, handler="other")

    for changes in (
        {"handler": "other"},
        {"user_id": "bob"},
        {"namespace": "extension:two"},
    ):
        with pytest.raises(PermissionError, match="another owner or handler"):
            await crud.save_scheduled_job(existing.copy(update=changes))
    assert await crud.get_scheduled_job(existing.id) == existing


@pytest.mark.anyio
async def test_scheduler_toggle_keeps_worker_alive_and_resumes_overdue_jobs(
    schedule_db, clock, settings: Settings, mocker: MockerFixture
):
    overdue = await crud.save_scheduled_job(job())
    completed = asyncio.Event()
    callback = mocker.AsyncMock(side_effect=lambda item: completed.set())
    maintenance = mocker.spy(service, "maintain_scheduled_job_runs")
    interruptions = mocker.spy(service, "interrupt_expired_scheduled_job_runs")
    polling = mocker.spy(service, "get_due_scheduled_jobs")
    worker = Scheduler()
    worker.register("core", "check", callback)
    settings.lnbits_running = True
    settings.lnbits_scheduler_enabled = False
    runner = asyncio.create_task(worker.run())
    try:
        await asyncio.sleep(0)
        assert not runner.done()
        maintenance.assert_not_awaited()
        interruptions.assert_not_awaited()
        polling.assert_not_awaited()
        callback.assert_not_awaited()
        assert await crud.get_scheduled_job(overdue.id) == overdue

        settings.lnbits_scheduler_enabled = True
        await asyncio.wait_for(completed.wait(), 3)
        await asyncio.wait_for(worker.running[overdue.id][1], 1)
        await worker.tick()
        callback.assert_awaited_once()
        stored = await crud.get_scheduled_job(overdue.id)
        assert stored and stored.next_run_at == NOW + 60
        assert stored.lease_token is None
        assert not runner.done()
    finally:
        runner.cancel()
        await asyncio.gather(runner, return_exceptions=True)


@pytest.mark.anyio
async def test_disabling_scheduler_allows_running_jobs_to_finish(
    schedule_db, clock, settings: Settings
):
    for job_id in ("first", "second"):
        await crud.save_scheduled_job(job(job_id))
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def callback(item):
        calls.append(item.id)
        started.set()
        await release.wait()

    worker = Scheduler(concurrency=1)
    worker.register("core", "check", callback)
    try:
        await worker.tick()
        await asyncio.wait_for(started.wait(), 1)
        settings.lnbits_scheduler_enabled = False
        await worker.tick()
        release.set()
        await asyncio.wait_for(worker.running["first"][1], 1)
        assert calls == ["first"]
        finished = await crud.get_scheduled_job("first")
        assert finished and finished.next_run_at == NOW + 60
        assert finished.lease_token is None
        pending = await crud.get_scheduled_job("second")
        assert pending and pending.next_run_at == NOW - 600
        assert pending.lease_token is None

        settings.lnbits_scheduler_enabled = True
        await worker.tick()
        await asyncio.wait_for(worker.running["second"][1], 1)
        assert calls == ["first", "second"]
    finally:
        release.set()
        await worker.stop()


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["get_due_scheduled_jobs", "claim_scheduled_job"])
async def test_disabling_scheduler_during_polling_preserves_due_job(
    schedule_db, clock, settings: Settings, mocker: MockerFixture, operation: str
):
    overdue = await crud.save_scheduled_job(job())
    original = getattr(service, operation)

    async def disable_after_operation(*args, **kwargs):
        result = await original(*args, **kwargs)
        settings.lnbits_scheduler_enabled = False
        return result

    mocker.patch.object(service, operation, side_effect=disable_after_operation)
    callback = mocker.AsyncMock()
    worker = Scheduler()
    worker.register("core", "check", callback)
    try:
        await worker.tick()
        callback.assert_not_awaited()
        assert worker.running == {}
        assert await crud.get_scheduled_job(overdue.id) == overdue

        mocker.patch.object(service, operation, original)
        settings.lnbits_scheduler_enabled = True
        await worker.tick()
        await asyncio.wait_for(worker.running[overdue.id][1], 1)
        callback.assert_awaited_once()
    finally:
        await worker.stop()


@pytest.mark.anyio
async def test_long_job_skips_overlap_across_workers(schedule_db, clock):
    await crud.save_scheduled_job(job())
    started = asyncio.Event()
    finish = asyncio.Event()
    calls = []

    async def callback(item):
        calls.append(item.id)
        started.set()
        await finish.wait()

    first, second = Scheduler(), Scheduler()
    first.register("core", "check", callback)
    second.register("core", "check", callback)
    try:
        await first.tick()
        await asyncio.wait_for(started.wait(), 1)
        clock.now += 40
        active = await crud.get_scheduled_job("test")
        assert active and active.lease_token
        assert await crud.renew_scheduled_job(
            "test", active.lease_token, clock.now, clock.now + 180
        )
        clock.now += 100
        await second.tick()
        assert second.running == {}
        assert calls == ["test"]
        finish.set()
        await asyncio.wait_for(first.running["test"][1], 1)
        stored = await crud.get_scheduled_job("test")
        assert stored and stored.next_run_at == NOW + 180
    finally:
        await first.stop()
        await second.stop()


@pytest.mark.anyio
async def test_failures_do_not_spin_and_jobs_run_concurrently(schedule_db, clock):
    for job_id in ("one", "two", "three"):
        await crud.save_scheduled_job(job(job_id))
    worker = Scheduler(concurrency=2)
    ready = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def callback(item):
        calls.append(item.id)
        if len(calls) == 2:
            ready.set()
        await release.wait()
        raise RuntimeError("callback error")

    worker.register("core", "check", callback)
    try:
        await worker.tick()
        await asyncio.wait_for(ready.wait(), 1)
        assert len(worker.running) == 2
        release.set()
        await asyncio.gather(*(task for _, task in worker.running.values()))
        for job_id in calls:
            stored = await crud.get_scheduled_job(job_id)
            assert stored and stored.next_run_at == NOW + 60
    finally:
        await worker.stop()


@pytest.mark.anyio
async def test_shutdown_preserves_claim_for_recovery(schedule_db, clock):
    await crud.save_scheduled_job(job())
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def callback(item):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    worker = Scheduler()
    worker.register("core", "check", callback)
    await worker.tick()
    await asyncio.wait_for(started.wait(), 1)
    runs = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert runs.data[0].status == "running"
    assert runs.data[0].finished_at is None
    await worker.stop()
    runs = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert runs.data[0].status == "cancelled"
    assert runs.data[0].finished_at == NOW
    assert stopped.is_set()
    stored = await crud.get_scheduled_job("test")
    assert stored and stored.lease_token and stored.next_run_at == NOW - 600
    assert await crud.get_due_scheduled_jobs(NOW + 59, 1) == []
    assert len(await crud.get_due_scheduled_jobs(NOW + 60, 1)) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("slow_cleanup", [False, True])
async def test_namespace_stop_bounds_wait_without_stopping_other_jobs(
    slow_cleanup: bool, schedule_db, clock, mocker: MockerFixture
):
    namespaces = {
        "user": "extension:one",
        "shared": "extension:one",
        "other": "extension:two",
        "core": "core",
    }
    for job_id, namespace in namespaces.items():
        await crud.save_scheduled_job(
            job(job_id).copy(
                update={
                    "namespace": namespace,
                    "user_id": "alice" if job_id == "user" else None,
                }
            )
        )
    mocker.patch.object(service, "check_schedule_access", mocker.AsyncMock())
    warning = mocker.patch.object(service.logger, "warning")
    started: set[str] = set()
    cleaning: set[str] = set()
    cleaned: set[str] = set()
    ready, release = asyncio.Event(), asyncio.Event()
    if not slow_cleanup:
        release.set()

    async def callback(item):
        started.add(item.id)
        if len(started) == len(namespaces):
            ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.add(item.id)
            await release.wait()
            cleaned.add(item.id)

    worker = Scheduler()
    for namespace in set(namespaces.values()):
        worker.register(namespace, "check", callback)
    try:
        await worker.tick()
        await asyncio.wait_for(ready.wait(), 1)
        timeout = 0.01 if slow_cleanup else 1
        await asyncio.wait_for(
            worker.stop_namespace("extension:one", timeout=timeout), 2
        )
        assert cleaning == {"user", "shared"}
        assert not worker.stopping
        assert set(worker.handlers) == {("extension:two", "check"), ("core", "check")}
        for job_id in ("user", "shared"):
            stored = await crud.get_scheduled_job(job_id)
            assert stored and stored.lease_token and stored.next_run_at == NOW - 600
            assert worker.running[job_id][1].done() is (not slow_cleanup)
        assert not worker.running["other"][1].done()
        assert not worker.running["core"][1].done()
        if slow_cleanup:
            assert not cleaned
            warning.assert_called_once_with(
                "Scheduler stop for {} exceeded {} seconds; {} jobs remain unfinished.",
                "extension:one",
                0.01,
                2,
            )
        else:
            assert cleaned == {"user", "shared"}
            warning.assert_not_called()
    finally:
        release.set()
        await asyncio.gather(
            *(
                task
                for item, task in worker.running.values()
                if item.namespace == "extension:one"
            ),
            return_exceptions=True,
        )
        await worker.stop()
    assert cleaned == set(namespaces)


@pytest.mark.anyio
async def test_heartbeat_renews_claim_and_pause_cancels_callback(
    schedule_db, clock, mocker: MockerFixture
):
    await crud.save_scheduled_job(job())
    started, renewed, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_renew = service.renew_scheduled_job

    async def renew(*args):
        result = await original_renew(*args)
        renewed.set()
        return result

    mocker.patch.object(service, "renew_scheduled_job", side_effect=renew)

    async def callback(item):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    worker = Scheduler(lease_seconds=3)
    worker.register("core", "check", callback)
    try:
        await worker.tick()
        await asyncio.wait_for(started.wait(), 1)
        clock.now += 1
        await asyncio.wait_for(renewed.wait(), 2)
        stored = await crud.get_scheduled_job("test")
        assert stored and stored.lease_until == clock.now + 3
        stored.enabled = False
        await crud.save_scheduled_job(stored)
        await asyncio.wait_for(worker.running["test"][1], 2)
        assert stopped.is_set()
        stored = await crud.get_scheduled_job("test")
        assert stored and not stored.enabled and stored.lease_token is None
        runs = await crud.get_scheduled_job_runs_paginated(
            Filters(model=ScheduledJobRunFilters)
        )
        assert runs.data[0].status == "cancelled"
    finally:
        await worker.stop()


@pytest.mark.anyio
async def test_concurrent_shutdown_waits_for_callback_cleanup(schedule_db, clock):
    await crud.save_scheduled_job(job())
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    cleaned = asyncio.Event()

    async def callback(item):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            cleaned.set()

    worker = Scheduler()
    worker.register("core", "check", callback)
    await worker.tick()
    await asyncio.wait_for(started.wait(), 1)
    first = asyncio.create_task(worker.stop())
    await asyncio.wait_for(cleaning.wait(), 1)
    second = asyncio.create_task(worker.stop())
    try:
        await asyncio.sleep(0)
        assert not first.done() and not second.done()
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert cleaned.is_set()
    finally:
        release.set()
        await asyncio.gather(first, second, return_exceptions=True)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error", [None, RuntimeError("private failure details"), asyncio.CancelledError()]
)
async def test_safe_scheduler_stop_handles_completion_and_errors(
    error: BaseException | None, mocker: MockerFixture
):
    stop = mocker.patch.object(
        service.scheduler, "stop", mocker.AsyncMock(side_effect=error)
    )
    warning = mocker.patch.object(service.logger, "warning")
    await service.stop_scheduler_safely()
    stop.assert_awaited_once()
    if error is None:
        warning.assert_not_called()
    else:
        warning.assert_called_once()
        assert "private failure details" not in str(warning.call_args)


@pytest.mark.anyio
async def test_safe_scheduler_stop_bounds_wait_and_preserves_cleanup(
    schedule_db, clock, mocker: MockerFixture
):
    await crud.save_scheduled_job(job())
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    cleaned = asyncio.Event()

    async def callback(item):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            cleaned.set()

    worker = Scheduler()
    mocker.patch.object(service, "scheduler", worker)
    warning = mocker.patch.object(service.logger, "warning")
    worker.register("core", "check", callback)
    await worker.tick()
    await asyncio.wait_for(started.wait(), 1)
    try:
        await asyncio.wait_for(service.stop_scheduler_safely(timeout=0.01), 1)
        assert cleaning.is_set() and not cleaned.is_set()
        assert not worker.running["test"][1].done()
        warning.assert_called_once_with(
            "Scheduler shutdown exceeded {} seconds; {} jobs remain unfinished.",
            0.01,
            1,
        )
        stored = await crud.get_scheduled_job("test")
        assert stored and stored.lease_token and stored.next_run_at == NOW - 600
    finally:
        release.set()
        await worker.stop()
    assert cleaned.is_set()


@pytest.mark.anyio
async def test_safe_scheduler_stop_logs_caller_cancellation_and_preserves_cleanup(
    mocker: MockerFixture,
):
    started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stop():
        started.set()
        await release.wait()
        finished.set()

    mocker.patch.object(service.scheduler, "stop", side_effect=stop)
    warning = mocker.patch.object(service.logger, "warning")
    caller = asyncio.create_task(service.stop_scheduler_safely())
    try:
        await asyncio.wait_for(started.wait(), 1)
        caller.cancel()
        await caller
        assert not caller.cancelled()
        assert not finished.is_set()
        warning.assert_called_once_with(
            "Scheduler shutdown wait was cancelled; "
            "cleanup continues in the background."
        )
    finally:
        release.set()
        await asyncio.wait_for(finished.wait(), 1)


@pytest.mark.anyio
async def test_safe_scheduler_stop_logs_wait_errors(mocker: MockerFixture):
    finished = asyncio.Event()
    stop = mocker.patch.object(
        service.scheduler, "stop", mocker.AsyncMock(side_effect=finished.set)
    )
    mocker.patch.object(
        service.asyncio, "wait", side_effect=RuntimeError("private failure details")
    )
    warning = mocker.patch.object(service.logger, "warning")

    await service.stop_scheduler_safely()
    await asyncio.wait_for(finished.wait(), 1)

    stop.assert_awaited_once()
    warning.assert_called_once_with("Scheduler shutdown failed.")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error", [None, RuntimeError("stop failed"), asyncio.CancelledError()]
)
async def test_app_shutdown_runs_cleanup_after_scheduler_stop_interruption(
    error: BaseException | None, mocker: MockerFixture
):
    mocker.patch("lnbits.app.enqueue_admin_notification")
    stop = mocker.patch.object(
        service.scheduler, "stop", mocker.AsyncMock(side_effect=error)
    )
    cancel_tasks = mocker.patch("lnbits.app.task_manager.cancel_all_tasks")
    cleanup = mocker.AsyncMock()
    mocker.patch(
        "lnbits.app.get_funding_source", return_value=SimpleNamespace(cleanup=cleanup)
    )
    await shutdown()
    stop.assert_awaited_once()
    cancel_tasks.assert_called_once()
    cleanup.assert_awaited_once()


@pytest.fixture
async def schedule_accounts(schedule_db, mocker: MockerFixture):
    async with schedule_db.connect() as conn:
        await m001_initial(conn)
        await m044_add_activated_to_accounts(conn)
        await conn.execute("INSERT INTO accounts (id) VALUES ('alice'), ('bob')")
    mocker.patch.object(user_crud, "db", schedule_db)
    mocker.patch.object(service, "get_account", user_crud.get_account)
    return schedule_db


@pytest.mark.anyio
@pytest.mark.parametrize("owner_state", ["deleted", "deactivated"])
async def test_inactive_owner_schedules_stop_accumulating_runs(
    schedule_accounts, clock, mocker: MockerFixture, owner_state
):
    original = {}
    for job_id, namespace, owner, handler, enabled in (
        ("orphan", "core", "alice", "check", True),
        ("other-handler", "extension:one", "alice", "other", True),
        ("other-extension", "extension:two", "alice", "check", True),
        ("paused", "core", "alice", "check", False),
        ("other-user", "core", "bob", "check", True),
        ("shared", "core", None, "check", True),
    ):
        original[job_id] = await crud.save_scheduled_job(
            job(job_id).copy(
                update={
                    "namespace": namespace,
                    "user_id": owner,
                    "handler": handler,
                    "enabled": enabled,
                    "next_run_at": NOW if job_id == "orphan" else NOW + 3600,
                }
            )
        )
    if owner_state == "deleted":
        await user_crud.delete_account("alice")
    else:
        await schedule_accounts.execute(
            "UPDATE accounts SET activated = false WHERE id = :id", {"id": "alice"}
        )
    worker = Scheduler()
    callback = mocker.AsyncMock()
    worker.register("core", "check", callback)
    try:
        await worker.tick()
        await asyncio.wait_for(worker.running["orphan"][1], 2)
        callback.assert_not_awaited()
        for job_id in ("orphan", "other-handler", "other-extension", "paused"):
            stored = await crud.get_scheduled_job(job_id)
            assert stored and not stored.enabled
        for job_id in ("other-user", "shared", "paused"):
            assert await crud.get_scheduled_job(job_id) == original[job_id]
        history = await crud.get_scheduled_job_runs_paginated(
            Filters(model=ScheduledJobRunFilters)
        )
        assert history.total == 1 and history.data[0].status == "failed"

        # Restoring the account must not automatically resume disabled jobs.
        await schedule_accounts.execute(
            "INSERT INTO accounts (id, activated) VALUES (:id, true) "
            "ON CONFLICT (id) DO UPDATE SET activated = true",
            {"id": "alice"},
        )
        for _ in range(2):
            clock.now += 60
            await worker.tick()
            assert not worker.running
            assert (
                await crud.get_scheduled_job_runs_paginated(
                    Filters(model=ScheduledJobRunFilters)
                )
                == history
            )
        callback.assert_not_awaited()
    finally:
        await worker.stop()


@pytest.mark.anyio
@pytest.mark.parametrize("owner_state", ["deleted", "deactivated"])
async def test_inactive_owner_heartbeat_disables_schedules_and_cancels_callback(
    schedule_accounts, clock, owner_state
):
    await crud.save_scheduled_job(job("running", user_id="alice"))
    await crud.save_scheduled_job(
        job("future", user_id="alice").copy(update={"next_run_at": NOW + 3600})
    )
    worker = Scheduler(lease_seconds=3)
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def callback(item):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    worker.register("core", "check", callback)
    try:
        await worker.tick()
        await asyncio.wait_for(started.wait(), 2)
        if owner_state == "deleted":
            await user_crud.delete_account("alice")
        else:
            await schedule_accounts.execute(
                "UPDATE accounts SET activated = false WHERE id = :id", {"id": "alice"}
            )
        await asyncio.wait_for(worker.running["running"][1], 3)
        assert cancelled.is_set()
        for job_id in ("running", "future"):
            stored = await crud.get_scheduled_job(job_id)
            assert stored and not stored.enabled and stored.lease_token is None
        history = await crud.get_scheduled_job_runs_paginated(
            Filters(model=ScheduledJobRunFilters)
        )
        assert history.total == 1 and history.data[0].status == "cancelled"
        clock.now += 60
        await worker.tick()
        assert not worker.running
        assert (
            await crud.get_scheduled_job_runs_paginated(
                Filters(model=ScheduledJobRunFilters)
            )
            == history
        )
    finally:
        await worker.stop()


@pytest.mark.anyio
async def test_revoked_grants_and_disabled_users(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_extensions_deactivate_all = False
    extension = SimpleNamespace(
        active=True,
        is_wasm=True,
        permissions=[
            ExtensionPermission(
                id="scheduler.user",
                policies=[{"handler": "check", "cron_expression": "* * * * *"}],
            )
        ],
    )
    enabled = SimpleNamespace(active=True)
    account = SimpleNamespace(activated=True)
    mocker.patch.object(
        service, "get_installed_extension", mocker.AsyncMock(return_value=extension)
    )
    mocker.patch.object(
        service, "get_user_extension", mocker.AsyncMock(return_value=enabled)
    )
    mocker.patch.object(service, "get_account", mocker.AsyncMock(return_value=account))
    config = job()
    grants = extension.permissions
    await check_schedule_access("extension:one", "alice", config)
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", None, config)
    extension.permissions = []
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", "alice", config)
    extension.permissions = grants
    enabled.active = False
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", "alice", config)
    enabled.active = True
    account.activated = False
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", "alice", config)
    with pytest.raises(PermissionError):
        await check_schedule_access("core", "alice", config)


@pytest.mark.anyio
@pytest.mark.parametrize("user_id", ["alice", None])
@pytest.mark.parametrize(
    "changes",
    [
        {"handler": "other"},
        {"cron_expression": "*/5 * * * *"},
        {"cron_expression": "*/30 * * * *"},
        {"timezone": "Europe/Bucharest"},
    ],
)
async def test_wasm_schedule_save_requires_approved_policy(
    user_id, changes, schedule_db, clock, wasm_schedule_grants, mocker: MockerFixture
):
    worker = Scheduler()
    for handler in ("check", "other"):
        worker.register("extension:one", handler, mocker.AsyncMock())
    expression = "*/10 * * * *" if user_id else "*/20 * * * *"
    config = ScheduleConfig(id="approved", handler="check", cron_expression=expression)
    saved = await worker.save("extension:one", config, user_id=user_id)
    for job_id in ("unapproved", saved.id):
        with pytest.raises(PermissionError, match="admin-approved"):
            await worker.save(
                "extension:one",
                config.copy(update={"id": job_id, **changes}),
                user_id=user_id,
            )
    assert await crud.get_scheduled_job(saved.id) == saved
    assert await crud.get_scheduled_job("unapproved") is None
    # Payload and pause state can still be changed without changing the schedule.
    updated = await worker.save(
        "extension:one",
        config.copy(update={"enabled": False, "payload_json": '{"threshold": 100}'}),
        user_id=user_id,
    )
    assert not updated.enabled and json.loads(updated.payload_json) == {
        "threshold": 100
    }


@pytest.mark.anyio
@pytest.mark.parametrize("user_id", ["alice", None])
@pytest.mark.parametrize(
    "changes",
    [
        {"handler": "other"},
        {"cron_expression": "*/30 * * * *"},
        {"timezone": "Europe/Bucharest"},
    ],
)
async def test_wasm_schedule_rechecks_policy_before_execution(
    user_id, changes, schedule_db, clock, wasm_schedule_grants, mocker: MockerFixture
):
    grant = wasm_schedule_grants.permissions[0 if user_id else 1]
    config = ScheduleConfig.parse_obj(grant.policies[0])
    worker = Scheduler()
    callback = mocker.AsyncMock()
    worker.register("extension:one", "check", callback)
    saved = await worker.save("extension:one", config, user_id=user_id)
    grant.policies[0].update(changes)
    try:
        assert saved.next_run_at is not None
        clock.now = saved.next_run_at
        await worker.tick()
        await asyncio.wait_for(
            asyncio.gather(*(task for _, task in worker.running.values())), 2
        )
        callback.assert_not_awaited()
        stored = await crud.get_scheduled_job(saved.id)
        assert stored and stored.lease_token is None and stored.enabled
        assert stored.next_run_at is not None
        assert stored.next_run_at > clock.now
    finally:
        await worker.stop()


@pytest.mark.anyio
@pytest.mark.parametrize("user_id", ["alice", None])
async def test_wasm_schedule_policy_revocation_cancels_running_callback(
    user_id, schedule_db, clock, wasm_schedule_grants
):
    grant = wasm_schedule_grants.permissions[0 if user_id else 1]
    config = ScheduleConfig.parse_obj(grant.policies[0])
    worker = Scheduler(lease_seconds=3)
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def callback(item):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    worker.register("extension:one", "check", callback)
    saved = await worker.save("extension:one", config, user_id=user_id)
    try:
        clock.now = saved.next_run_at
        await worker.tick()
        await asyncio.wait_for(started.wait(), 2)
        # Keep the permission but revoke this handler's policy.
        grant.policies = [{"handler": "other", "cron_expression": "* * * * *"}]
        await asyncio.wait_for(worker.running[saved.id][1], 3)
        assert cancelled.is_set()
        stored = await crud.get_scheduled_job(saved.id)
        assert stored and stored.lease_token is None
    finally:
        await worker.stop()


@pytest.mark.anyio
@pytest.mark.parametrize("user_id", ["alice", None])
async def test_wasm_schedule_cannot_use_other_scope_policy(
    user_id, wasm_schedule_grants
):
    other_grant = wasm_schedule_grants.permissions[1 if user_id else 0]
    config = ScheduleConfig.parse_obj(other_grant.policies[0])
    with pytest.raises(PermissionError, match="admin-approved"):
        await check_schedule_access("extension:one", user_id, config)


@pytest.mark.anyio
async def test_python_schedule_does_not_require_wasm_policies(wasm_schedule_grants):
    wasm_schedule_grants.is_wasm = False
    wasm_schedule_grants.permissions = []
    await check_schedule_access("extension:one", "alice", job())


@pytest.mark.anyio
async def test_user_extension_disable_cancels_only_its_running_jobs(
    extension_job_scopes: dict[str, tuple[str, str | None]], clock
):
    worker = Scheduler(concurrency=len(extension_job_scopes), lease_seconds=3)
    started = {job_id: asyncio.Event() for job_id in extension_job_scopes}
    release = asyncio.Event()
    cancelled: set[str] = set()
    affected = {"alice:first", "alice:second"}

    async def callback(item: ScheduledJob):
        started[item.id].set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.add(item.id)
            raise

    for namespace in ("extension:one", "extension:two"):
        worker.register(namespace, "check", callback)
    for job_id, (namespace, user_id) in extension_job_scopes.items():
        await worker.save(
            namespace,
            ScheduleConfig(id=job_id, handler="check", cron_expression="* * * * *"),
            user_id=user_id,
        )

    try:
        clock.now += 60
        await worker.tick()
        await asyncio.wait_for(
            asyncio.gather(*(event.wait() for event in started.values())), 3
        )
        result = await extension_api.api_disable_extension("one", AccountId(id="alice"))
        assert result.success
        await asyncio.wait_for(
            asyncio.gather(*(worker.running[job_id][1] for job_id in affected)), 3
        )
        assert cancelled == affected
        for job_id in extension_job_scopes.keys() - affected:
            assert not worker.running[job_id][1].done()
        for job_id in affected:
            stored = await crud.get_scheduled_job(job_id)
            assert stored and stored.enabled and stored.lease_token is None
            assert stored.namespace == "extension:one" and stored.user_id == "alice"
            assert stored.next_run_at == NOW + 120
        release.set()
        await asyncio.wait_for(
            asyncio.gather(*(task for _, task in worker.running.values())), 3
        )
        assert cancelled == affected
    finally:
        release.set()
        await worker.stop()


@pytest.mark.anyio
async def test_user_extension_reenable_resumes_jobs_and_preserves_manual_pauses(
    extension_job_scopes: dict[str, tuple[str, str | None]], clock
):
    worker = Scheduler(concurrency=len(extension_job_scopes) + 1)
    calls: list[str] = []

    async def callback(item: ScheduledJob):
        calls.append(item.id)

    for namespace in ("extension:one", "extension:two"):
        worker.register(namespace, "check", callback)
    for job_id, (namespace, user_id) in extension_job_scopes.items():
        await worker.save(
            namespace,
            ScheduleConfig(id=job_id, handler="check", cron_expression="* * * * *"),
            user_id=user_id,
        )
    paused = await worker.save(
        "extension:one",
        ScheduleConfig(
            id="alice:paused",
            handler="check",
            cron_expression="* * * * *",
            enabled=False,
        ),
        user_id="alice",
    )

    try:
        result = await extension_api.api_disable_extension("one", AccountId(id="alice"))
        assert result.success
        clock.now += 60
        await worker.tick()
        await asyncio.wait_for(
            asyncio.gather(*(task for _, task in worker.running.values())), 3
        )
        assert sorted(calls) == ["alice:other-extension", "bob", "shared"]
        for job_id in ("alice:first", "alice:second"):
            stored = await crud.get_scheduled_job(job_id)
            assert stored and stored.enabled and stored.next_run_at == NOW + 120
        assert await crud.get_scheduled_job(paused.id) == paused

        result = await extension_api.api_enable_extension("one", AccountId(id="alice"))
        assert result.success
        clock.now += 60
        await worker.tick()
        await asyncio.wait_for(
            asyncio.gather(*(task for _, task in worker.running.values())), 3
        )
        assert sorted(calls) == sorted(
            [*extension_job_scopes, "alice:other-extension", "bob", "shared"]
        )
        assert await crud.get_scheduled_job(paused.id) == paused
    finally:
        await worker.stop()


@pytest.mark.anyio
async def test_config_update_keeps_claim_and_new_schedule(schedule_db):
    await crud.save_scheduled_job(job())
    claimed = await crud.claim_scheduled_job("test", "claim", NOW, NOW + 60)
    assert claimed
    changed = claimed.copy(
        update={"cron_expression": "0 9 * * *", "next_run_at": NOW + 9 * 3600}
    )
    await crud.save_scheduled_job(changed)
    await crud.finish_scheduled_job(claimed, NOW + 60)
    stored = await crud.get_scheduled_job("test")
    assert stored and stored.next_run_at == NOW + 9 * 3600
    assert stored.lease_token is None


@pytest.mark.anyio
async def test_core_save_preserves_payload_and_rejects_impossible_dates(
    schedule_db, clock
):
    worker = Scheduler()

    async def callback(item):
        pass

    worker.register("core", "check", callback)
    payload = {"message": "<b>BTC &amp; USD</b> €"}
    saved = await worker.save(
        "core",
        ScheduleConfig(
            id="core:payload",
            handler="check",
            cron_expression="*/10 * * * *",
            payload_json=json.dumps(payload),
        ),
    )
    assert json.loads(saved.payload_json) == payload
    assert saved.next_run_at == NOW + 600
    with pytest.raises(ValueError, match="no occurrence"):
        await worker.save(
            "core", ScheduleConfig(handler="check", cron_expression="0 0 31 FEB *")
        )
    with pytest.raises(ValueError, match="not registered"):
        await worker.save(
            "core", ScheduleConfig(handler="unknown", cron_expression="* * * * *")
        )


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["succeeded", "failed", "skipped"])
async def test_scheduler_records_execution_outcomes(schedule_db, clock, outcome):
    await crud.save_scheduled_job(job(payload_json='{"secret":"hidden-payload"}'))
    worker = Scheduler()

    async def callback(_job):
        clock.now += 2.25
        if outcome == "failed":
            raise ValueError("secret=hidden-exception-secret")

    if outcome != "skipped":
        worker.register("core", "check", callback)
    try:
        await worker.tick()
        await worker.running["test"][1]
        page = await crud.get_scheduled_job_runs_paginated(
            Filters(model=ScheduledJobRunFilters)
        )
        assert page.total == 1
        run = page.data[0]
        assert run.job_id == "test"
        assert run.scheduled_at == NOW - 600
        assert run.started_at == NOW
        assert run.finished_at == clock.now
        assert run.status == outcome
        assert "hidden-" not in run.json()
        assert "lease_token" not in run.dict()
        if outcome == "succeeded":
            assert run.error_summary is None
        elif outcome == "failed":
            assert run.error_summary == "ValueError: secret=[redacted]"
        else:
            assert run.error_summary
        if outcome != "skipped":
            assert run.finished_at is not None
            assert run.finished_at - run.started_at == 2.25
    finally:
        await worker.stop()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            ValueError("Remote service refused the request."),
            "ValueError: Remote service refused the request.",
        ),
        (
            PermissionError("Schedule owner is not active."),
            "PermissionError: Schedule owner is not active.",
        ),
        (TimeoutError(), "TimeoutError"),
        (
            RuntimeError(
                "api_key=private-key token=private-token password=private-password"
            ),
            "RuntimeError: api_key=[redacted] token=[redacted] password=[redacted]",
        ),
        (
            RuntimeError("Authorization: Bearer abc.def"),
            "RuntimeError: Authorization=[redacted]",
        ),
        (
            RuntimeError("Authorization: Basic dXNlcjpwYXNzd29yZA=="),
            "RuntimeError: Authorization=[redacted]",
        ),
        (RuntimeError("Bearer abc.def"), "RuntimeError: Bearer [redacted]"),
        (
            RuntimeError('{"secret": "hidden-payload with spaces"}'),
            'RuntimeError: {"secret"=[redacted]}',
        ),
        (
            RuntimeError("password='hidden password with spaces'"),
            "RuntimeError: password=[redacted]",
        ),
        (RuntimeError('secret="hidden\\"password"'), "RuntimeError: secret=[redacted]"),
        (RuntimeError("preimage=" + "a" * 64), "RuntimeError: preimage=[redacted]"),
        (RuntimeError("a" * 64), "RuntimeError: [redacted-hex]"),
        (
            RuntimeError("x" * 475 + " " + "a" * 64),
            ("RuntimeError: " + "x" * 475 + " [redacted-hex]")[:500],
        ),
        (RuntimeError("x" * 600), "RuntimeError: " + "x" * 486),
        (
            Trap(
                "error while executing at wasm backtrace:\n"
                "    0: 0x21 - <unknown>!<wasm function 0>\n\n"
                "Caused by:\n    wasm trap: wasm `unreachable` instruction executed\n"
            ),
            "Trap: wasm trap: wasm `unreachable` instruction executed",
        ),
    ],
)
async def test_scheduler_records_sanitized_failure_details(
    schedule_db, clock, mocker: MockerFixture, error: Exception, expected: str
):
    await crud.save_scheduled_job(job(payload_json='{"secret":"hidden-payload"}'))
    worker = Scheduler()
    warning = mocker.patch.object(service.logger, "warning")

    async def callback(_job):
        raise error

    worker.register("core", "check", callback)
    try:
        await worker.tick()
        await worker.running["test"][1]
        page = await crud.get_scheduled_job_runs_paginated(
            Filters(model=ScheduledJobRunFilters)
        )
        assert page.total == 1
        run = page.data[0]
        assert run.status == "failed"
        assert run.error_summary == expected
        assert "hidden-payload" not in run.json()
        warning.assert_called_once_with(
            "Scheduled job {} failed ({}); next attempt follows its cron schedule.",
            "test",
            expected,
        )
        stored = await crud.get_scheduled_job("test")
        assert stored and stored.lease_token is None
        assert stored.next_run_at == NOW + 60
    finally:
        await worker.stop()


@pytest.mark.anyio
async def test_history_cleanup_and_interrupted_runs_have_separate_intervals(
    schedule_db, clock, settings
):
    settings.lnbits_scheduler_history_max_runs_per_extension = 1
    worker = Scheduler()
    await worker.tick()

    await history_run("old", finished_at=NOW - 1)
    await history_run("new")
    await crud.save_scheduled_job(job("abandoned"))
    claimed = await crud.claim_scheduled_job("abandoned", "claim", NOW, NOW + 60)
    assert claimed
    run = await crud.create_scheduled_job_run(claimed, NOW)
    assert await crud.delete_scheduled_job("abandoned", "core", None, NOW + 60)

    for elapsed, status in ((59, "running"), (60, "interrupted"), (899, "interrupted")):
        clock.now = NOW + elapsed
        await worker.tick()
        page = await crud.get_scheduled_job_runs_paginated(
            Filters(model=ScheduledJobRunFilters)
        )
        assert {entry.job_id for entry in page.data} == {"old", "new", "abandoned"}
        assert next(entry for entry in page.data if entry.id == run.id).status == status

    clock.now = NOW + 15 * 60
    await worker.tick()
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert {entry.job_id for entry in page.data} == {"new", "abandoned"}


@pytest.mark.anyio
async def test_history_recovers_expired_runs_and_survives_job_deletion(schedule_db):
    await crud.save_scheduled_job(job())
    claimed = await crud.claim_scheduled_job("test", "first", NOW, NOW + 60)
    assert claimed
    run = await crud.create_scheduled_job_run(claimed, NOW)
    await service.interrupt_expired_scheduled_job_runs(NOW + 30)
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert page.data[0].status == "running"

    # A second worker takes over. The first attempt must no longer look active.
    claimed = await crud.claim_scheduled_job("test", "second", NOW + 60, NOW + 120)
    assert claimed
    active = await crud.create_scheduled_job_run(claimed, NOW + 60)
    await service.interrupt_expired_scheduled_job_runs(NOW + 61)
    # A late result from the old attempt cannot overwrite an interrupted result.
    await crud.finish_scheduled_job_run(run.id, "succeeded", NOW + 62)
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    by_id = {entry.id: entry for entry in page.data}
    assert by_id[run.id].status == "interrupted"
    assert by_id[run.id].finished_at is None
    assert by_id[active.id].status == "running"

    await crud.finish_scheduled_job_run(active.id, "succeeded", NOW + 63)
    assert await crud.delete_scheduled_job("test", "core", None, NOW + 120)
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert page.total == 2
    await service.maintain_scheduled_job_runs(NOW + 7 * 86400 + 64)
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert page.total == 0


@pytest.mark.anyio
@pytest.mark.parametrize("retention_days", [1, 7])
async def test_history_retention_preserves_live_and_recently_finished_runs(
    schedule_db, settings, retention_days
):
    settings.lnbits_scheduler_history_retention_days = retention_days
    age = (retention_days + 1) * 86400
    for job_id in ("active", "recent", "expired"):
        await crud.save_scheduled_job(job(job_id))
        claimed = await crud.claim_scheduled_job(job_id, job_id, NOW, NOW + age + 60)
        assert claimed
        run = await crud.create_scheduled_job_run(claimed, NOW)
        if job_id != "active":
            await crud.finish_scheduled_job_run(
                run.id, "succeeded", NOW + age if job_id == "recent" else NOW + 1
            )
    await service.maintain_scheduled_job_runs(NOW + age + 1)
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert {run.job_id for run in page.data} == {"active", "recent"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation", ["create_scheduled_job_run", "finish_scheduled_job_run"]
)
async def test_history_write_failure_does_not_change_execution(
    schedule_db, clock, mocker, operation
):
    await crud.save_scheduled_job(job())
    mocker.patch.object(
        service, operation, side_effect=RuntimeError("private-db-error")
    )
    callback = mocker.AsyncMock()
    worker = Scheduler()
    worker.register("core", "check", callback)
    try:
        await worker.tick()
        await worker.running["test"][1]
        callback.assert_awaited_once()
        stored = await crud.get_scheduled_job("test")
        assert stored and stored.next_run_at == NOW + 60
        assert stored.lease_token is None
    finally:
        await worker.stop()


@pytest.mark.anyio
async def test_history_migration_preserves_existing_jobs(schedule_db):
    database = Database("history_migration")
    try:
        async with database.connect() as conn:
            await m054_create_scheduled_jobs(conn)
            await conn.execute("""
                INSERT INTO scheduled_jobs (id, namespace, handler, cron_expression)
                VALUES ('existing', 'core', 'check', '* * * * *')
            """)
            await m055_create_scheduled_job_runs(conn)
            rows: list[dict] = await conn.fetchall("SELECT id FROM scheduled_jobs")
            assert [row["id"] for row in rows] == ["existing"]
            assert await conn.fetchall("SELECT id FROM scheduled_job_runs") == []
    finally:
        await database.engine.dispose()


@pytest.mark.parametrize(
    "field, default",
    [
        ("lnbits_scheduler_history_retention_days", 7),
        ("lnbits_scheduler_history_failed_retention_days", 30),
        ("lnbits_scheduler_history_max_runs_per_user", 1000),
        ("lnbits_scheduler_history_max_runs_per_extension", 1000),
    ],
)
def test_scheduler_history_retention_setting(field, default):
    assert SchedulerSettings().lnbits_scheduler_enabled is True
    assert getattr(SchedulerSettings(), field) == default
    assert getattr(SchedulerSettings.parse_obj({field: 42}), field) == 42
    with pytest.raises(ValidationError):
        SchedulerSettings.parse_obj({field: 0})


@pytest.mark.anyio
async def test_history_failed_retention_is_longer_and_preserves_running(schedule_db):
    for status in (
        "succeeded",
        "failed",
        "cancelled",
        "interrupted",
        "skipped",
        "running",
    ):
        await crud.save_scheduled_job(job(status))
        claimed = await crud.claim_scheduled_job(status, status, NOW, NOW + 32 * 86400)
        assert claimed
        run = await crud.create_scheduled_job_run(claimed, NOW)
        if status != "running":
            await crud.finish_scheduled_job_run(run.id, status, NOW)

    for age, expected in (
        (8, {"failed", "running"}),
        (30, {"failed", "running"}),
        (31, {"running"}),
    ):
        await service.maintain_scheduled_job_runs(NOW + age * 86400)
        page = await crud.get_scheduled_job_runs_paginated(
            Filters(model=ScheduledJobRunFilters)
        )
        assert {run.job_id for run in page.data} == expected


async def history_run(
    job_id,
    *,
    namespace="extension:one",
    user_id=None,
    handler="check",
    status: ScheduledJobRunStatus = "succeeded",
    finished_at=NOW,
):
    stored = await crud.save_scheduled_job(
        job(job_id).copy(
            update={"namespace": namespace, "user_id": user_id, "handler": handler}
        )
    )
    claimed = await crud.claim_scheduled_job(
        stored.id, stored.id, NOW - 100, NOW + 3600
    )
    assert claimed
    run = await crud.create_scheduled_job_run(claimed, NOW - 100)
    if status != "running":
        await crud.finish_scheduled_job_run(run.id, status, finished_at)
        await crud.finish_scheduled_job(claimed, NOW + 86400)
    return run


@pytest.mark.anyio
async def test_history_user_cap_spans_handlers_sources_and_deleted_jobs(
    schedule_db, settings, clock
):
    settings.lnbits_scheduler_history_max_runs_per_user = 3
    await history_run(
        "old-failure", user_id="alice", status="failed", finished_at=NOW - 4
    )
    await history_run(
        "old-success", user_id="alice", handler="other", finished_at=NOW - 3
    )
    await history_run(
        "new-success", user_id="alice", namespace="extension:two", finished_at=NOW - 2
    )
    await history_run(
        "new-failure",
        user_id="alice",
        namespace="core",
        status="failed",
        finished_at=NOW - 1,
    )
    await history_run("bob", user_id="bob")
    await history_run("shared")
    for index in range(4):
        await history_run(f"active-{index}", user_id="alice", status="running")
    for job_id in ("old-failure", "old-success", "new-success", "new-failure"):
        stored = await crud.get_scheduled_job(job_id)
        assert stored
        assert await crud.delete_scheduled_job(job_id, stored.namespace, "alice", NOW)

    worker = Scheduler()
    await worker.tick()
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    active_ids = {f"active-{index}" for index in range(4)}
    assert {run.job_id for run in page.data} == {
        "old-failure",
        "new-success",
        "new-failure",
        "bob",
        "shared",
        *active_ids,
    }
    assert all("user_id" not in run.dict() for run in page.data)

    # The same worker applies a lowered limit on its next maintenance tick.
    settings.lnbits_scheduler_history_max_runs_per_user = 1
    clock.now += 15 * 60
    await worker.tick()
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert {run.job_id for run in page.data} == {
        "new-failure",
        "bob",
        "shared",
        *active_ids,
    }


@pytest.mark.anyio
async def test_history_shared_extension_cap_is_separate_from_users_and_core(
    schedule_db, settings
):
    settings.lnbits_scheduler_history_max_runs_per_extension = 1
    for namespace in ("extension:one", "extension:two", "core"):
        await history_run(
            f"{namespace}-old",
            namespace=namespace,
            status="failed",
            finished_at=NOW - 1,
        )
        await history_run(f"{namespace}-new", namespace=namespace)
    await history_run("user-first", user_id="alice")
    await history_run("user-second", user_id="alice")
    await history_run("active", status="running")

    await service.maintain_scheduled_job_runs(NOW)
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert {run.job_id for run in page.data} == {
        "extension:one-old",
        "extension:two-old",
        "core-old",
        "core-new",
        "user-first",
        "user-second",
        "active",
    }


@pytest.mark.anyio
async def test_history_cap_removes_oldest_failures_when_all_runs_failed(
    schedule_db, settings
):
    settings.lnbits_scheduler_history_max_runs_per_extension = 2
    for index in range(4):
        await history_run(str(index), status="failed", finished_at=NOW + index)
    await service.maintain_scheduled_job_runs(NOW + 4)
    page = await crud.get_scheduled_job_runs_paginated(
        Filters(model=ScheduledJobRunFilters)
    )
    assert {run.job_id for run in page.data} == {"2", "3"}
