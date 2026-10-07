import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import extensions as extension_crud
from lnbits.core.crud import scheduler as crud
from lnbits.core.migrations import (
    m001_initial,
    m020_add_column_column_to_user_extensions,
    m049_add_permissions_to_user_extensions,
    m054_create_scheduled_jobs,
)
from lnbits.core.models.extensions import Extension, ExtensionPermission, UserExtension
from lnbits.core.models.scheduler import ScheduleConfig, ScheduledJob
from lnbits.core.models.users import AccountId
from lnbits.core.services import scheduler as service
from lnbits.core.services.scheduler import Scheduler, check_schedule_access
from lnbits.core.views import extension_api
from lnbits.db import DB_TYPE, SQLITE, Database
from lnbits.settings import Settings
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
            ExtensionPermission(id="scheduler.user"),
            ExtensionPermission(id="scheduler.extension"),
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
    assert len(await crud.list_scheduled_jobs("extension:one", "alice")) == 1
    assert await crud.list_scheduled_jobs("extension:one", None) == []
    assert await crud.list_scheduled_jobs("extension:two", "alice") == []
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
    await worker.stop()
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
    original_renew = crud.renew_scheduled_job

    async def renew(*args):
        result = await original_renew(*args)
        renewed.set()
        return result

    mocker.patch.object(crud, "renew_scheduled_job", side_effect=renew)

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
async def test_safe_scheduler_stop_preserves_caller_cancellation(
    mocker: MockerFixture,
):
    started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stop():
        started.set()
        await release.wait()
        finished.set()

    mocker.patch.object(service.scheduler, "stop", side_effect=stop)
    caller = asyncio.create_task(service.stop_scheduler_safely())
    try:
        await asyncio.wait_for(started.wait(), 1)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        assert not finished.is_set()
    finally:
        release.set()
        await asyncio.wait_for(finished.wait(), 1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error", [RuntimeError("stop failed"), asyncio.CancelledError()]
)
async def test_app_shutdown_runs_cleanup_after_scheduler_stop_interruption(
    error: BaseException, mocker: MockerFixture
):
    from lnbits.app import shutdown

    mocker.patch("lnbits.app.enqueue_admin_notification")
    mocker.patch("lnbits.app.stop_scheduler_safely", side_effect=error)
    cancel_tasks = mocker.patch("lnbits.app.task_manager.cancel_all_tasks")
    cleanup = mocker.AsyncMock()
    mocker.patch(
        "lnbits.app.get_funding_source", return_value=SimpleNamespace(cleanup=cleanup)
    )
    with pytest.raises(type(error)):
        await shutdown()
    cancel_tasks.assert_called_once()
    cleanup.assert_awaited_once()


@pytest.mark.anyio
async def test_revoked_grants_and_disabled_users(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_extensions_deactivate_all = False
    extension = SimpleNamespace(
        active=True,
        is_wasm=True,
        permissions=[ExtensionPermission(id="scheduler.user")],
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
    await check_schedule_access("extension:one", "alice")
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", None)
    extension.permissions = []
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", "alice")
    extension.permissions = [ExtensionPermission(id="scheduler.user")]
    enabled.active = False
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", "alice")
    enabled.active = True
    account.activated = False
    with pytest.raises(PermissionError):
        await check_schedule_access("extension:one", "alice")
    with pytest.raises(PermissionError):
        await check_schedule_access("core", "alice")


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
