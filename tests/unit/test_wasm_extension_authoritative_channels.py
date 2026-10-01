import asyncio
import json
import multiprocessing
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from lnbits.core.wasm_ext.api import authoritative_channels as channels
from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.core.wasm_ext.wasm.config import WasmAuthoritativeChannelConfig
from lnbits.settings import Settings


@pytest.fixture(autouse=True)
def local_actor_owner(mocker):
    # Transport fencing has separate database-backed broker tests.
    mocker.patch.object(
        channels, "_validate_current_channel_permissions", return_value=None
    )
    mocker.patch.object(channels.broker, "in_handler", return_value=True)
    mocker.patch.object(channels.broker, "check_owner", return_value=True)
    mocker.patch.object(channels.broker, "is_owner", return_value=True)
    mocker.patch.object(channels.broker, "epoch", return_value=1)
    mocker.patch.object(channels.broker, "assert_owner", return_value=1)
    mocker.patch.object(channels.broker, "publish_state", return_value=None)
    mocker.patch.object(channels.broker, "recover_state", return_value=None)


def _clear_extension_database_cache(extension_id: str) -> None:
    """Drop the cached engine and schema flags, as a fresh worker would."""
    loop = asyncio.get_running_loop()
    key = storage_crud._database_key(extension_id)
    storage_crud._databases.get(loop, {}).pop(key, None)
    initialized = storage_crud._initialized_databases.get(loop, set())
    for init_key in list(initialized):
        if init_key[0] == key:
            initialized.discard(init_key)


def _wait_for_admission_in_child(data_folder, extension_id, output):
    async def run():
        sequence = await channels.reserve_authoritative_job(
            extension_id,
            "room",
            "child-job",
            max_active_rooms=1,
            max_queue_depth=3,
        )
        output.put(("reserved", sequence))
        job: Any = SimpleNamespace(
            room_id="room",
            admission_sequence=sequence,
            limits={"wasm_runtime_max_execution_ms": 1000},
            extension=SimpleNamespace(
                config=SimpleNamespace(
                    authoritative_channel=SimpleNamespace(max_queue_depth=3)
                )
            ),
        )
        await channels._wait_for_job_turn(
            await channels._database(extension_id),
            job,
        )
        output.put(("ready", sequence))
        await channels.release_authoritative_job(extension_id, "child-job")

    storage_crud.settings.lnbits_data_folder = data_folder
    asyncio.run(run())


@pytest.mark.anyio
async def test_room_lease_renews_after_one_third_and_stops_promptly(mocker):
    update_times = []
    intervals = []
    stop = asyncio.Event()

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, *_args, **_kwargs):
            update_times.append(time.monotonic())
            return SimpleNamespace(rowcount=1)

    class FakeDatabase:
        def connect(self):
            return FakeConnection()

    async def controlled_wait_for(awaitable, *, timeout):
        intervals.append(timeout)
        if len(intervals) == 1:
            awaitable.close()
            raise asyncio.TimeoutError
        stop.set()
        await awaitable

    mocker.patch.object(channels, "_table_ref", return_value="rooms")
    mocker.patch.object(channels.asyncio, "wait_for", controlled_wait_for)
    await channels._renew_room_lease(
        cast(Any, FakeDatabase()), "room", "lease", 600, stop
    )

    assert intervals == [0.2, 0.2]
    assert stop.is_set()
    assert len(update_times) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body_error,renewal_error",
    [
        (None, RuntimeError("renewal failed")),
        (ValueError("body failed"), RuntimeError("renewal failed")),
        (ValueError("body failed"), asyncio.CancelledError()),
    ],
)
async def test_room_lease_releases_when_renewal_fails(
    mocker, body_error, renewal_error
):
    class Result:
        rowcount = 1

        def close(self):
            pass

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        class Raw:
            async def execute(self, *_args, **_kwargs):
                return Result()

        conn = Raw()

    class Database:
        def connect(self):
            return Connection()

    @asynccontextmanager
    async def transaction(_connection):
        yield

    mocker.patch.object(channels, "_ensure_room", AsyncMock())
    mocker.patch.object(channels, "_transaction", transaction)
    mocker.patch.object(channels, "_table_ref", return_value="rooms")
    mocker.patch.object(
        channels,
        "_renew_room_lease",
        AsyncMock(side_effect=renewal_error),
    )
    release = mocker.patch.object(channels, "_release_room_lease", AsyncMock())

    expected_error = body_error or renewal_error
    with pytest.raises(type(expected_error), match=str(expected_error)):
        async with channels._room_lease(cast(Any, Database()), "room", "owner", 10_000):
            if body_error:
                raise body_error

    release.assert_awaited_once_with(mocker.ANY, "room", mocker.ANY)


@pytest.mark.anyio
async def test_ephemeral_dispatch_does_not_send_access_token_to_broker(mocker):
    extension_id = f"token{uuid4().hex[:8]}"
    mocker.patch.object(channels, "validate_authoritative_channel_limits")
    mocker.patch.object(
        channels, "get_ephemeral_authoritative_extension_generation", return_value=1
    )
    extension: Any = SimpleNamespace(
        id=extension_id,
        config=SimpleNamespace(
            authoritative_channel=SimpleNamespace(persistence="ephemeral")
        ),
    )
    mocker.patch.object(channels.broker, "in_handler", return_value=False)
    call = mocker.patch.object(channels.broker, "call", return_value={"ok": True})

    await channels.run_authoritative_channel_export(
        extension,
        "room",
        "owner",
        "serialize",
        {},
        limits={},
        action="api",
        invoke_options={"access_token": "secret"},
        permissions=[],
        policy_generation=1,
    )

    assert "access_token" not in call.await_args.args[2]["invoke_options"]


def _schedule_fixture() -> tuple[Any, Any, Any]:
    extension: Any = SimpleNamespace(id=f"schedule{uuid4().hex[:8]}")
    job: Any = SimpleNamespace(
        extension=extension,
        room_id="room",
        owner_id="owner",
        limits={},
        permissions=[],
        policy_generation=1,
    )
    room = SimpleNamespace(
        scheduler_task=None,
        connections={"connection": int(time.time() * 1000) + 60_000},
        generation="generation",
        owner_id="owner",
        state=SimpleNamespace(last_schedule_ms=0),
    )
    channel = SimpleNamespace(on_schedule="scheduled_tick", schedule_interval_ms=1000)
    return job, room, channel


@pytest.mark.anyio
async def test_ephemeral_schedule_recovers_and_resets_rejection_count(mocker):
    job, room, channel = _schedule_fixture()
    key = (job.extension.id, job.room_id)
    mocker.patch.object(channels.settings, "lnbits_running", True)
    mocker.patch.object(channels.asyncio, "sleep", AsyncMock())
    mocker.patch.object(channels, "_check_actor_ownership")
    mocker.patch.dict(channels._ephemeral_rooms, {key: room})
    warnings = mocker.patch.object(channels.logger, "warning")
    calls = 0

    async def dispatch(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls in {1, 3, 4}:
            raise channels.AuthoritativeChannelRejectedError("private guest detail")
        if calls == 5:
            channels._ephemeral_rooms.pop(key, None)
        return {"ok": True}

    mocker.patch.object(channels, "run_authoritative_channel_export", dispatch)

    channels._start_ephemeral_room_schedule(job, room, channel)
    await asyncio.wait_for(room.scheduler_task, timeout=1)

    assert calls == 5
    assert warnings.call_count == 3
    assert "private guest detail" not in str(warnings.call_args_list)


@pytest.mark.anyio
async def test_ephemeral_schedule_stops_after_bounded_guest_rejections(mocker):
    job, room, channel = _schedule_fixture()
    mocker.patch.object(channels.settings, "lnbits_running", True)
    mocker.patch.object(channels.asyncio, "sleep", AsyncMock())
    mocker.patch.object(channels, "_check_actor_ownership")
    mocker.patch.dict(
        channels._ephemeral_rooms, {(job.extension.id, job.room_id): room}
    )
    warnings = mocker.patch.object(channels.logger, "warning")
    dispatch = mocker.patch.object(
        channels,
        "run_authoritative_channel_export",
        AsyncMock(side_effect=channels.AuthoritativeChannelRejectedError("secret")),
    )

    channels._start_ephemeral_room_schedule(job, room, channel)
    await asyncio.wait_for(room.scheduler_task, timeout=1)

    assert dispatch.await_count == 3
    assert warnings.call_count == 3
    warning = str(warnings.call_args_list[0])
    assert "scheduled_tick" in warning
    assert job.extension.id in warning
    assert "room" in warning
    assert "AuthoritativeChannelRejectedError" in warning
    assert "secret" not in warning


@pytest.mark.anyio
@pytest.mark.parametrize("failure_location", ["fence", "dispatch"])
async def test_ephemeral_schedule_stops_on_permission_error(mocker, failure_location):
    job, room, channel = _schedule_fixture()
    mocker.patch.object(channels.settings, "lnbits_running", True)
    mocker.patch.object(channels.asyncio, "sleep", AsyncMock())
    check_owner = mocker.patch.object(channels, "_check_actor_ownership")
    if failure_location == "fence":
        check_owner.side_effect = PermissionError("private fence detail")
    dispatch = mocker.patch.object(
        channels,
        "run_authoritative_channel_export",
        AsyncMock(side_effect=PermissionError("private fence detail")),
    )
    mocker.patch.dict(
        channels._ephemeral_rooms, {(job.extension.id, job.room_id): room}
    )
    warnings = mocker.patch.object(channels.logger, "warning")

    channels._start_ephemeral_room_schedule(job, room, channel)
    await asyncio.wait_for(room.scheduler_task, timeout=1)

    assert dispatch.await_count == (0 if failure_location == "fence" else 1)
    assert warnings.call_count == 1
    warning = str(warnings.call_args)
    assert "scheduled_tick" in warning
    assert job.extension.id in warning
    assert "room" in warning
    assert "PermissionError" in warning
    assert "private fence detail" not in warning


def test_ephemeral_channels_require_no_deployment_flag(settings: Settings, monkeypatch):
    channel = WasmAuthoritativeChannelConfig.parse_obj(
        {
            "authorizeConnection": "authorize",
            "onEvent": "event",
            "ownerContext": {"table": "rooms", "idParam": "id"},
            "eventFields": ["move"],
            "maxEventsPerSecond": 10,
            "maxQueueDepth": 4,
            "maxActiveRooms": 2,
            "persistence": "ephemeral",
        }
    )
    limits = {
        "wasm_runtime_max_execution_ms": 1000,
        "wasm_runtime_max_authoritative_rooms": 4,
        "wasm_runtime_max_authoritative_queue_depth": 8,
        "wasm_runtime_max_authoritative_events_per_second": 20,
        "wasm_runtime_max_authoritative_schedule_rate_hz": 10,
    }
    channels.validate_authoritative_channel_limits(channel, limits)
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    channels.validate_authoritative_channel_limits(channel, limits)


@pytest.mark.anyio
async def test_ephemeral_authoritative_room_is_bounded_owner_scoped_and_sql_free(
    settings: Settings, mocker
):
    extension_id = f"ephemeral{uuid4().hex[:8]}"
    policy_generation = channels.get_ephemeral_authoritative_extension_generation(
        extension_id
    )
    channel = WasmAuthoritativeChannelConfig.parse_obj(
        {
            "authorizeConnection": "authorize",
            "onEvent": "event",
            "ownerContext": {"table": "rooms", "idParam": "id"},
            "eventFields": ["move"],
            "maxEventsPerSecond": 10,
            "maxQueueDepth": 4,
            "maxActiveRooms": 1,
            "persistence": "ephemeral",
        }
    )
    extension: Any = SimpleNamespace(
        id=extension_id,
        config=SimpleNamespace(authoritative_channel=channel),
    )
    limits = {
        "wasm_runtime_max_execution_ms": 1000,
        "wasm_runtime_max_authoritative_rooms": 4,
        "wasm_runtime_max_authoritative_queue_depth": 8,
        "wasm_runtime_max_authoritative_events_per_second": 20,
        "wasm_runtime_max_authoritative_schedule_rate_hz": 10,
        "wasm_runtime_max_authoritative_state_bytes": 1024,
    }
    database = mocker.patch.object(
        channels,
        "_database",
        mocker.AsyncMock(side_effect=AssertionError("unexpected host database access")),
    )
    mocker.patch.object(
        channels,
        "_invoke_room_job",
        side_effect=[
            {"ok": True, "data": {"state": {"position": 0}}},
            {"ok": True, "data": {"state": {"position": 1}}},
            {"ok": True, "data": {"state": {"position": 0}}},
        ],
    )
    room_id = "room-a"
    try:
        assert await channels.reserve_authoritative_connection(
            extension_id,
            room_id,
            "owner-a",
            "connection-a",
            max_active_rooms=1,
            max_connections_per_room=2,
            persistence="ephemeral",
        )
        await channels.run_authoritative_channel_export(
            extension,
            room_id,
            "owner-a",
            "authorize",
            {},
            limits=limits,
            action="authorize",
            permissions=[],
            policy_generation=policy_generation,
        )
        generation = channels.get_authoritative_channel_generation(
            extension_id, room_id, "owner-a"
        )
        await channels.release_authoritative_connection(
            extension_id,
            "connection-a",
            room_id=room_id,
            persistence="ephemeral",
        )
        result = await channels.run_authoritative_channel_export(
            extension,
            room_id,
            "owner-a",
            "event",
            {"event": {"move": "left"}},
            limits=limits,
            action="event",
            principal_id="principal-a",
            client_sequence=1,
            room_generation=generation,
            permissions=[],
            policy_generation=policy_generation,
        )
        assert result["_hostSequence"] == 1
        state = await channels.get_authoritative_channel_state(
            extension_id, room_id, "owner-a", persistence="ephemeral"
        )
        assert state.sequence == 1
        assert state.snapshot == {"position": 1}
        assert len(state.event_timestamps) == 1
        assert (
            await channels.get_authoritative_principal_sequence(
                extension_id,
                room_id,
                "principal-a",
                persistence="ephemeral",
            )
            == 1
        )
        with pytest.raises(PermissionError, match="owner does not match"):
            await channels.get_authoritative_channel_state(
                extension_id, room_id, "owner-b", persistence="ephemeral"
            )
        with pytest.raises(ValueError, match="sequence is stale"):
            await channels.run_authoritative_channel_export(
                extension,
                room_id,
                "owner-a",
                "event",
                {"event": {"move": "left"}},
                limits=limits,
                action="event",
                principal_id="principal-a",
                client_sequence=1,
                room_generation=generation,
                permissions=[],
                policy_generation=policy_generation,
            )
        with pytest.raises(PermissionError, match="generation expired"):
            await channels.run_authoritative_channel_export(
                extension,
                room_id,
                "owner-a",
                "event",
                {"event": {"move": "left"}},
                limits=limits,
                action="event",
                principal_id="principal-a",
                client_sequence=2,
                room_generation="stale-generation",
                permissions=[],
                policy_generation=policy_generation,
            )

        await channels.run_authoritative_channel_export(
            extension,
            "room-b",
            "owner-a",
            "authorize",
            {},
            limits=limits,
            action="authorize",
            permissions=[],
            policy_generation=policy_generation,
        )
        with pytest.raises(PermissionError, match="room was not found"):
            await channels.get_authoritative_channel_state(
                extension_id, room_id, "owner-a", persistence="ephemeral"
            )
        database.assert_not_awaited()
    finally:
        entries = [
            entry
            for (queued_extension_id, _), entry in channels._channel_queues.items()
            if queued_extension_id == extension_id
        ]
        channels.invalidate_ephemeral_authoritative_extension(extension_id)
        await asyncio.gather(
            *(entry.worker for entry in entries), return_exceptions=True
        )


@pytest.mark.anyio
async def test_ephemeral_invalidation_rejects_running_and_queued_jobs(
    settings: Settings, mocker
):
    extension_id = f"ephemeralstop{uuid4().hex[:8]}"
    policy_generation = channels.get_ephemeral_authoritative_extension_generation(
        extension_id
    )
    room_id = "room"
    channel = WasmAuthoritativeChannelConfig.parse_obj(
        {
            "authorizeConnection": "authorize",
            "onEvent": "event",
            "ownerContext": {"table": "rooms", "idParam": "id"},
            "eventFields": ["move"],
            "maxEventsPerSecond": 10,
            "maxQueueDepth": 4,
            "maxActiveRooms": 1,
            "persistence": "ephemeral",
        }
    )
    extension: Any = SimpleNamespace(
        id=extension_id,
        config=SimpleNamespace(authoritative_channel=channel),
    )
    limits = {
        "wasm_runtime_max_execution_ms": 1000,
        "wasm_runtime_max_authoritative_rooms": 4,
        "wasm_runtime_max_authoritative_queue_depth": 8,
        "wasm_runtime_max_authoritative_events_per_second": 20,
        "wasm_runtime_max_authoritative_state_bytes": 1024,
    }
    room = channels._get_ephemeral_room(
        extension_id, room_id, "owner-a", max_active_rooms=1, create=True
    )
    room.state = channels.AuthoritativeChannelState(
        sequence=0,
        version=1,
        last_schedule_ms=0,
        snapshot={},
        has_snapshot=True,
        event_timestamps=[],
    )
    started = asyncio.Event()

    async def block_job(*_args):
        started.set()
        await asyncio.Event().wait()

    mocker.patch.object(channels, "_invoke_room_job", side_effect=block_job)
    first = second = None
    entry = None
    try:
        first = asyncio.create_task(
            channels.run_authoritative_channel_export(
                extension,
                room_id,
                "owner-a",
                "event",
                {"event": {"move": "left"}},
                limits=limits,
                action="event",
                principal_id="principal-a",
                client_sequence=1,
                room_generation=room.generation,
                permissions=[],
                policy_generation=policy_generation,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        second = asyncio.create_task(
            channels.run_authoritative_channel_export(
                extension,
                room_id,
                "owner-a",
                "event",
                {"event": {"move": "right"}},
                limits=limits,
                action="event",
                principal_id="principal-a",
                client_sequence=2,
                room_generation=room.generation,
                permissions=[],
                policy_generation=policy_generation,
            )
        )
        await asyncio.sleep(0)
        assert room.pending_jobs == 2
        entry = channels._channel_queues.get((extension_id, room_id))

        channels.invalidate_ephemeral_authoritative_extension(extension_id)
        results = await asyncio.gather(first, second, return_exceptions=True)

        assert all(isinstance(result, PermissionError) for result in results)
        assert (extension_id, room_id) not in channels._ephemeral_rooms
        assert (extension_id, room_id) not in channels._channel_queues
        with pytest.raises(PermissionError, match="policy changed"):
            await channels.run_authoritative_channel_export(
                extension,
                room_id,
                "owner-a",
                "authorize",
                {},
                limits=limits,
                action="authorize",
                permissions=[],
                policy_generation=policy_generation,
            )
    finally:
        entry = entry or channels._channel_queues.get((extension_id, room_id))
        channels.invalidate_ephemeral_authoritative_extension(extension_id)
        if entry:
            await asyncio.gather(entry.worker, return_exceptions=True)
        tasks = [task for task in (first, second) if task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.anyio
async def test_ephemeral_result_commit_failure_does_not_publish_state(
    settings: Settings, mocker
):
    extension_id = f"ephemeralresult{uuid4().hex[:8]}"
    policy_generation = channels.get_ephemeral_authoritative_extension_generation(
        extension_id
    )
    channel = WasmAuthoritativeChannelConfig.parse_obj(
        {
            "authorizeConnection": "authorize",
            "onEvent": "event",
            "ownerContext": {"table": "rooms", "idParam": "id"},
            "eventFields": ["move"],
            "maxEventsPerSecond": 10,
            "maxQueueDepth": 4,
            "maxActiveRooms": 2,
            "resultTable": "game_results",
            "resultField": "result",
            "persistence": "ephemeral",
        }
    )
    extension: Any = SimpleNamespace(
        id=extension_id,
        config=SimpleNamespace(authoritative_channel=channel),
    )
    limits = {
        "wasm_runtime_max_execution_ms": 1000,
        "wasm_runtime_max_authoritative_rooms": 4,
        "wasm_runtime_max_authoritative_queue_depth": 8,
        "wasm_runtime_max_authoritative_events_per_second": 20,
        "wasm_runtime_max_authoritative_state_bytes": 1024,
    }

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class Database:
        def connect(self):
            return Connection()

    @asynccontextmanager
    async def transaction(_connection):
        yield

    mocker.patch.object(
        channels, "_database", mocker.AsyncMock(return_value=Database())
    )
    mocker.patch.object(channels, "_transaction", transaction)
    insert_result = mocker.patch.object(
        channels,
        "storage_insert_immutable_row",
        mocker.AsyncMock(side_effect=ValueError("result commit failed")),
    )
    mocker.patch.object(
        channels,
        "_invoke_room_job",
        side_effect=[
            {"ok": True, "data": {"state": {"position": 0}}},
            {
                "ok": True,
                "data": {
                    "state": {
                        "position": 1,
                        "result": {"winner": "player-a"},
                    }
                },
            },
        ],
    )
    key = (extension_id, "room")
    try:
        await channels.run_authoritative_channel_export(
            extension,
            "room",
            "owner-a",
            "authorize",
            {},
            limits=limits,
            action="authorize",
            permissions=[],
            policy_generation=policy_generation,
        )
        generation = channels.get_authoritative_channel_generation(
            extension_id, "room", "owner-a"
        )
        with pytest.raises(ValueError, match="result commit failed"):
            await channels.run_authoritative_channel_export(
                extension,
                "room",
                "owner-a",
                "event",
                {"event": {"move": "left"}},
                limits=limits,
                action="event",
                principal_id="principal-a",
                client_sequence=1,
                room_generation=generation,
                permissions=[],
                policy_generation=policy_generation,
            )

        state = await channels.get_authoritative_channel_state(
            extension_id, "room", "owner-a", persistence="ephemeral"
        )
        assert state.sequence == 0
        assert state.version == 1
        assert state.snapshot == {"position": 0}
        assert (
            await channels.get_authoritative_principal_sequence(
                extension_id,
                "room",
                "principal-a",
                persistence="ephemeral",
            )
            == 0
        )
        insert_result.assert_awaited_once()
    finally:
        entry = channels._channel_queues.get(key)
        channels.invalidate_ephemeral_authoritative_extension(extension_id)
        if entry:
            await asyncio.gather(entry.worker, return_exceptions=True)


@pytest.mark.anyio
async def test_authoritative_capacity_is_shared_and_expires_with_disconnect(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"cap{uuid4().hex[:8]}"

    assert await channels.reserve_authoritative_connection(
        extension_id,
        "room-a",
        "owner-a",
        "connection-a",
        max_active_rooms=1,
        max_connections_per_room=1,
    )
    assert not await channels.reserve_authoritative_connection(
        extension_id,
        "room-b",
        "owner-b",
        "connection-b",
        max_active_rooms=1,
        max_connections_per_room=1,
    )
    assert not await channels.reserve_authoritative_connection(
        extension_id,
        "room-a",
        "owner-a",
        "connection-c",
        max_active_rooms=1,
        max_connections_per_room=1,
    )

    await channels.release_authoritative_connection(extension_id, "connection-a")
    assert await channels.reserve_authoritative_connection(
        extension_id,
        "room-b",
        "owner-b",
        "connection-b",
        max_active_rooms=1,
        max_connections_per_room=1,
    )
    await channels.release_authoritative_connection(extension_id, "connection-b")


@pytest.mark.anyio
async def test_authoritative_queue_capacity_is_shared_between_workers(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"queue{uuid4().hex[:8]}"

    assert await channels.reserve_authoritative_job(
        extension_id, "room-a", "job-a", max_active_rooms=1, max_queue_depth=1
    )
    assert await channels.reserve_authoritative_job(
        extension_id, "room-a", "job-b", max_active_rooms=1, max_queue_depth=1
    )
    assert not await channels.reserve_authoritative_job(
        extension_id, "room-a", "job-c", max_active_rooms=1, max_queue_depth=1
    )
    assert not await channels.reserve_authoritative_job(
        extension_id, "room-b", "job-d", max_active_rooms=1, max_queue_depth=1
    )

    await channels.release_authoritative_job(extension_id, "job-a")
    await channels.release_authoritative_job(extension_id, "job-b")
    assert await channels.reserve_authoritative_job(
        extension_id, "room-b", "job-e", max_active_rooms=1, max_queue_depth=1
    )
    await channels.release_authoritative_job(extension_id, "job-e")


@pytest.mark.anyio
async def test_authoritative_admission_order_survives_worker_cache_restart(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"order{uuid4().hex[:8]}"
    first = await channels.reserve_authoritative_job(
        extension_id, "room", "job-first", max_active_rooms=1, max_queue_depth=3
    )

    _clear_extension_database_cache(extension_id)
    second = await channels.reserve_authoritative_job(
        extension_id, "room", "job-second", max_active_rooms=1, max_queue_depth=3
    )
    assert first == 1 and second == 2

    database = await channels._database(extension_id)
    job: Any = SimpleNamespace(
        room_id="room",
        admission_sequence=second,
        limits={"wasm_runtime_max_execution_ms": 1000},
        extension=SimpleNamespace(
            config=SimpleNamespace(
                authoritative_channel=SimpleNamespace(max_queue_depth=3)
            )
        ),
    )
    gate = asyncio.create_task(channels._wait_for_job_turn(database, job))
    await asyncio.sleep(0.03)
    assert not gate.done()
    await channels.release_authoritative_job(extension_id, "job-first")
    await gate
    await channels.release_authoritative_job(extension_id, "job-second")


@pytest.mark.anyio
async def test_authoritative_concurrent_admissions_get_unique_order(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"parallel{uuid4().hex[:8]}"
    sequences = await asyncio.gather(
        *(
            channels.reserve_authoritative_job(
                extension_id,
                "room",
                f"job-{index}",
                max_active_rooms=1,
                max_queue_depth=16,
            )
            for index in range(12)
        )
    )
    assert None not in sequences
    assert sorted(cast(list[int], sequences)) == list(range(1, 13))


@pytest.mark.anyio
async def test_authoritative_order_is_shared_across_processes(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"workers{uuid4().hex[:8]}"
    first = await channels.reserve_authoritative_job(
        extension_id, "room", "parent-job", max_active_rooms=1, max_queue_depth=3
    )
    assert first == 1
    context = multiprocessing.get_context("fork")
    output = context.Queue()
    child = context.Process(
        target=_wait_for_admission_in_child,
        args=(str(tmp_path), extension_id, output),
    )
    child.start()
    assert output.get(timeout=10) == ("reserved", 2)
    await channels.release_authoritative_job(extension_id, "parent-job")
    assert output.get(timeout=10) == ("ready", 2)
    child.join(timeout=10)
    assert child.exitcode == 0


@pytest.mark.anyio
async def test_authoritative_room_snapshot_survives_host_cache_restart(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"restart{uuid4().hex[:8]}"
    database = await channels._database(extension_id)
    rooms = channels._table_ref(database, channels._ROOMS_TABLE)
    async with database.connect() as conn:
        await conn.execute(
            f"""INSERT INTO {rooms}
                (room_id, owner_id, sequence, version, snapshot_json,
                 last_activity_ms)
                VALUES (:room_id, :owner_id, 7, 3, :snapshot, :now_ms)""",  # noqa: S608
            {
                "room_id": "room-a",
                "owner_id": "owner-a",
                "snapshot": json.dumps({"round": 2, "score": 13}),
                "now_ms": int(time.time() * 1000),
            },
        )

    _clear_extension_database_cache(extension_id)

    state = await channels.get_authoritative_channel_state(
        extension_id, "room-a", "owner-a"
    )

    assert state.sequence == 7
    assert state.version == 3
    assert state.snapshot == {"round": 2, "score": 13}


@pytest.mark.anyio
async def test_committed_result_is_inserted_immutable_in_same_transaction(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path / "data")
    Path(settings.lnbits_data_folder).mkdir()
    settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
    extension_id = f"result{uuid4().hex[:8]}"
    schema_path = tmp_path / "wasm_extensions" / extension_id / "storage"
    schema_path.mkdir(parents=True)
    (schema_path / "schema.json").write_text(
        json.dumps(
            {
                "tables": {
                    "game_results": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "scope_id", "type": "string"},
                            {"name": "amount_msat", "type": "integer"},
                            {"name": "note", "type": "string"},
                        ]
                    }
                }
            }
        )
    )
    database = await channels._database(extension_id)
    rooms = channels._table_ref(database, channels._ROOMS_TABLE)
    result_table = "game_results"
    result_table_ref = channels._table_ref(database, result_table)
    async with database.connect() as conn:
        await conn.execute(f"""CREATE TABLE {result_table_ref} (
                id TEXT PRIMARY KEY, scope_id TEXT NOT NULL,
                amount_msat BIGINT NOT NULL, note TEXT NOT NULL,
                __lnbits_owner_id__ TEXT NOT NULL,
                __lnbits_version__ BIGINT NOT NULL DEFAULT 1,
                __lnbits_immutable__ BOOLEAN NOT NULL DEFAULT false
            )""")
        await conn.execute(f"""INSERT INTO {rooms} (room_id, owner_id, lease_owner)
                VALUES ('room', 'owner', 'lease')""")  # noqa: S608

    await channels._save_room_state(
        database,
        extension_id,
        "room",
        "owner",
        "lease",
        sequence=3,
        snapshot={
            "round": 5,
            "result": {
                "scope_id": "room",
                "amount_msat": 7000,
                "note": "<b>won</b>",
            },
        },
        has_snapshot=True,
        update_sequence=True,
        principal_id=None,
        client_sequence=None,
        result_table=result_table,
    )

    async with database.connect() as conn:
        result = await conn.fetchone(
            f"SELECT * FROM {result_table_ref} WHERE id = 'room'"  # noqa: S608
        )
        room = await conn.fetchone(
            f"SELECT snapshot_json FROM {rooms} WHERE room_id = 'room'"  # noqa: S608
        )
    assert bool(result["__lnbits_immutable__"])
    assert result["amount_msat"] == 7000
    assert result["note"] == "won"
    assert json.loads(room["snapshot_json"])["result"]["scope_id"] == "room"
    with pytest.raises(ValueError, match="conflicts with an existing immutable row"):
        await channels._save_room_state(
            database,
            extension_id,
            "room",
            "owner",
            "lease",
            sequence=4,
            snapshot={
                "round": 6,
                "result": {
                    "scope_id": "room",
                    "amount_msat": 8000,
                    "note": "changed",
                },
            },
            has_snapshot=True,
            update_sequence=True,
            principal_id=None,
            client_sequence=None,
            result_table=result_table,
        )
    state = await channels.get_authoritative_channel_state(
        extension_id, "room", "owner"
    )
    assert state.sequence == 3
    assert state.snapshot["result"]["amount_msat"] == 7000

    with pytest.raises(channels.AuthoritativeChannelLeaseError):
        await channels._save_room_state(
            database,
            extension_id,
            "lost-room",
            "owner",
            "expired-lease",
            sequence=1,
            snapshot={
                "result": {
                    "scope_id": "lost-room",
                    "amount_msat": 1000,
                    "note": "lost",
                },
            },
            has_snapshot=True,
            update_sequence=True,
            principal_id=None,
            client_sequence=None,
            result_table=result_table,
        )
    async with database.connect() as conn:
        leaked_result = await conn.fetchone(
            f"SELECT * FROM {result_table_ref} WHERE id = 'lost-room'"  # noqa: S608
        )
    assert leaked_result is None


@pytest.mark.anyio
async def test_stale_authoritative_rooms_and_client_sequences_are_reaped(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"cleanup{uuid4().hex[:8]}"
    database = await channels._database(extension_id)
    rooms = channels._table_ref(database, channels._ROOMS_TABLE)
    clients = channels._table_ref(database, channels._CLIENTS_TABLE)
    order = channels._table_ref(database, channels._ORDER_TABLE)
    old_ms = int(time.time() * 1000) - channels._ROOM_RETENTION_MS - 1000
    async with database.connect() as conn:
        await conn.execute(
            f"""INSERT INTO {rooms}
                (room_id, owner_id, last_activity_ms) VALUES ('old', 'owner', :old)""",  # noqa: S608
            {"old": old_ms},
        )
        await conn.execute(f"""INSERT INTO {clients}
                (room_id, principal_id, last_client_sequence)
                VALUES ('old', 'principal', 4)""")  # noqa: S608
        await conn.execute(
            f"INSERT INTO {order} (room_id, next_sequence) VALUES ('old', 4)"  # noqa: S608
        )

    assert await channels.reserve_authoritative_job(
        extension_id, "new", "job", max_active_rooms=1, max_queue_depth=1
    )
    async with database.connect() as conn:
        assert not await conn.fetchone(
            f"SELECT room_id FROM {rooms} WHERE room_id = 'old'"  # noqa: S608
        )
        assert not await conn.fetchone(
            f"SELECT room_id FROM {clients} WHERE room_id = 'old'"  # noqa: S608
        )
        assert not await conn.fetchone(
            f"SELECT room_id FROM {order} WHERE room_id = 'old'"  # noqa: S608
        )
    await channels.release_authoritative_job(extension_id, "job")


@pytest.mark.anyio
async def test_authoritative_events_commit_snapshots_and_client_sequences(
    tmp_path: Path, settings: Settings, mocker
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"events{uuid4().hex[:8]}"
    channel = WasmAuthoritativeChannelConfig.parse_obj(
        {
            "authorizeConnection": "authorize",
            "onEvent": "handle_event",
            "onSchedule": None,
            "ownerContext": {"table": "rooms", "idParam": "id"},
            "resultTable": None,
            "resultField": "result",
            "eventFields": ["move"],
            "scheduleIntervalMs": None,
            "maxEventsPerSecond": 10,
            "maxQueueDepth": 4,
            "maxActiveRooms": 2,
        }
    )
    extension: Any = SimpleNamespace(
        id=extension_id,
        config=SimpleNamespace(authoritative_channel=channel),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.api.authoritative_channels._invoke_room_job",
        side_effect=[
            {"ok": True, "data": {"state": {"position": 0}}},
            {"ok": True, "data": {"state": {"position": 1}}},
        ],
    )
    limits = {
        "wasm_runtime_max_execution_ms": 1000,
        "wasm_runtime_max_authoritative_rooms": 4,
        "wasm_runtime_max_authoritative_queue_depth": 8,
        "wasm_runtime_max_authoritative_events_per_second": 20,
        "wasm_runtime_max_authoritative_schedule_rate_hz": 10,
        "wasm_runtime_max_authoritative_state_bytes": 1024,
    }
    key = (extension_id, "room-1")

    try:
        await channels.run_authoritative_channel_export(
            extension,
            "room-1",
            "owner-1",
            "authorize",
            {},
            limits=limits,
            action="authorize",
        )
        await channels.run_authoritative_channel_export(
            extension,
            "room-1",
            "owner-1",
            "handle_event",
            {"event": {"move": "left"}},
            limits=limits,
            action="event",
            principal_id="principal-1",
            client_sequence=1,
            connection_id="connection-1",
            received_at_ns=1,
        )
        state = await channels.get_authoritative_channel_state(
            extension_id, "room-1", "owner-1"
        )

        assert state.sequence == 1
        assert state.snapshot == {"position": 1}
        assert (
            await channels.get_authoritative_principal_sequence(
                extension_id, "room-1", "principal-1"
            )
            == 1
        )
    finally:
        entry = channels._channel_queues.pop(key, None)
        if entry:
            entry.worker.cancel()
            await asyncio.gather(entry.worker, return_exceptions=True)


@pytest.mark.anyio
async def test_cancelled_channel_export_releases_its_queue_reservation(
    tmp_path: Path, settings: Settings, mocker
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"cancel{uuid4().hex[:8]}"
    room_id = "room"
    database = await channels._database(extension_id)
    jobs = channels._table_ref(database, channels._JOBS_TABLE)
    release = asyncio.Event()

    async def block(job):
        await release.wait()
        return {"ok": True, "data": {"state": {}}}

    mocker.patch.object(channels, "_execute_channel_job", side_effect=block)
    channel = SimpleNamespace(
        authorize_connection="authorize",
        on_event=None,
        on_schedule=None,
        max_active_rooms=1,
        max_queue_depth=2,
        max_events_per_second=10,
        schedule_interval_ms=None,
    )
    extension: Any = SimpleNamespace(
        id=extension_id, config=SimpleNamespace(authoritative_channel=channel)
    )
    limits = {
        "wasm_runtime_max_execution_ms": 1000,
        "wasm_runtime_max_authoritative_rooms": 4,
        "wasm_runtime_max_authoritative_queue_depth": 4,
        "wasm_runtime_max_authoritative_events_per_second": 10,
        "wasm_runtime_max_authoritative_schedule_rate_hz": 10,
    }

    task = asyncio.create_task(
        channels.run_authoritative_channel_export(
            extension,
            room_id,
            "owner",
            "authorize",
            {},
            limits=limits,
            action="authorize",
        )
    )
    reserved = None
    for _ in range(100):
        async with database.connect() as conn:
            reserved = await conn.fetchone(f"SELECT job_id FROM {jobs}")  # noqa: S608
        if reserved:
            break
        await asyncio.sleep(0.01)
    assert reserved

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    release.set()

    async with database.connect() as conn:
        assert not await conn.fetchone(f"SELECT job_id FROM {jobs}")  # noqa: S608


@pytest.mark.anyio
async def test_ephemeral_crashed_worker_connections_expire_and_release_capacity():
    ext = f"expire{uuid4().hex[:8]}"
    try:
        assert await channels.reserve_authoritative_connection(
            ext,
            "old",
            "owner",
            "socket",
            max_active_rooms=1,
            max_connections_per_room=1,
            persistence="ephemeral",
        )
        channels._ephemeral_rooms[(ext, "old")].connections["socket"] = 0
        assert not await channels.renew_authoritative_connection(
            ext,
            "old",
            "socket",
            persistence="ephemeral",
        )
        assert await channels.reserve_authoritative_connection(
            ext,
            "replacement",
            "owner",
            "fresh",
            max_active_rooms=1,
            max_connections_per_room=1,
            persistence="ephemeral",
        )
        assert (ext, "old") not in channels._ephemeral_rooms
    finally:
        channels.invalidate_ephemeral_authoritative_extension(ext)


@pytest.mark.anyio
async def test_ephemeral_existing_room_lookup_skips_cross_room_sweep(mocker):
    ext = f"hotpath{uuid4().hex[:8]}"
    sweep = mocker.patch.object(channels, "_prune_ephemeral_rooms")
    try:
        room = channels._get_ephemeral_room(
            ext, "room", "owner", max_active_rooms=2, create=True
        )
        sweep.reset_mock()
        # An existing room must not pay for the cross-room sweep on the hot path.
        assert (
            channels._get_ephemeral_room(
                ext, "room", "owner", max_active_rooms=2, create=True
            )
            is room
        )
        sweep.assert_not_called()
        # Creating a room still sweeps so per-extension counts stay accurate.
        channels._get_ephemeral_room(
            ext, "second", "owner", max_active_rooms=2, create=True
        )
        sweep.assert_called_once()
    finally:
        channels.invalidate_ephemeral_authoritative_extension(ext)


@pytest.mark.anyio
async def test_ephemeral_actor_restores_snapshot_with_new_generation(mocker):
    ext = f"restore{uuid4().hex[:8]}"
    state = {
        "sequence": 7,
        "version": 4,
        "last_schedule_ms": 123,
        "snapshot": {"kills": ["kill-1"]},
        "has_snapshot": True,
        "event_timestamps": [],
    }
    recovery = mocker.patch.object(channels.broker, "recover_state", return_value=state)
    try:
        await channels._restore_ephemeral_room(ext, "room", "owner", 1)
        room = channels._ephemeral_rooms[(ext, "room")]
        assert room.state.sequence == 7
        assert room.state.snapshot == {"kills": ["kill-1"]}
        assert not room.connections and not room.principal_sequences
        generation = room.generation
        await channels._restore_ephemeral_room(ext, "room", "owner", 1)
        assert room.generation == generation
        recovery.assert_awaited_once()
    finally:
        channels.invalidate_ephemeral_authoritative_extension(ext)


@pytest.mark.parametrize("action", ["event", "authorize", "api", "schedule"])
@pytest.mark.parametrize("persistence", ["ephemeral", "durable"])
def test_invocation_generation_is_available_to_ephemeral_guests_only(
    action, persistence
):
    job: Any = SimpleNamespace(
        extension=SimpleNamespace(id="ext"),
        room_id="room",
        action=action,
        persistence=persistence,
        actor_generation="fresh",
        payload={"event": {}, "principalRole": "member"},
        principal_id="principal",
        connection_id="connection",
        client_sequence=1,
        received_at_ns=1,
    )
    state = channels.AuthoritativeChannelState(0, 0, 0, None, False, [])
    payload = channels._invocation_payload(job, 1, state, 100)
    context = payload if action in {"event", "schedule"} else payload["_authoritative"]
    assert context.get("generation") == (
        "fresh" if persistence == "ephemeral" else None
    )
