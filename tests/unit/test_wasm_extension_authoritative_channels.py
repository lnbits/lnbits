import asyncio
import json
import multiprocessing
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from lnbits.core.wasm_ext.api import authoritative_channels as channels
from lnbits.core.wasm_ext.wasm.config import WasmAuthoritativeChannelConfig
from lnbits.settings import Settings


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
        await channels._wait_for_job_turn(
            await channels._database(extension_id),
            SimpleNamespace(
                room_id="room",
                admission_sequence=sequence,
                limits={"wasm_runtime_max_execution_ms": 1000},
                extension=SimpleNamespace(
                    config=SimpleNamespace(
                        authoritative_channel=SimpleNamespace(max_queue_depth=3)
                    )
                ),
            ),
        )
        output.put(("ready", sequence))
        await channels.release_authoritative_job(extension_id, "child-job")

    channels.settings.lnbits_database_url = None
    channels.settings.lnbits_data_folder = data_folder
    asyncio.run(run())


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
    settings.lnbits_database_url = None
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"order{uuid4().hex[:8]}"
    first = await channels.reserve_authoritative_job(
        extension_id, "room", "job-first", max_active_rooms=1, max_queue_depth=3
    )

    loop = asyncio.get_running_loop()
    key = (
        extension_id,
        settings.lnbits_database_url or "",
        str(settings.lnbits_data_folder),
    )
    channels._databases.get(loop, {}).pop(key, None)
    channels._initialized_databases.get(loop, set()).discard(key)
    second = await channels.reserve_authoritative_job(
        extension_id, "room", "job-second", max_active_rooms=1, max_queue_depth=3
    )
    assert first == 1 and second == 2

    database = await channels._database(extension_id)
    gate = asyncio.create_task(
        channels._wait_for_job_turn(
            database,
            SimpleNamespace(
                room_id="room",
                admission_sequence=second,
                limits={"wasm_runtime_max_execution_ms": 1000},
                extension=SimpleNamespace(
                    config=SimpleNamespace(
                        authoritative_channel=SimpleNamespace(max_queue_depth=3)
                    )
                ),
            ),
        )
    )
    await asyncio.sleep(0.03)
    assert not gate.done()
    await channels.release_authoritative_job(extension_id, "job-first")
    await gate
    await channels.release_authoritative_job(extension_id, "job-second")


@pytest.mark.anyio
async def test_authoritative_concurrent_admissions_get_unique_order(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_database_url = None
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
    assert sorted(sequences) == list(range(1, 13))


@pytest.mark.anyio
async def test_authoritative_order_is_shared_across_processes(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_database_url = None
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

    loop = asyncio.get_running_loop()
    key = (
        extension_id,
        settings.lnbits_database_url or "",
        str(settings.lnbits_data_folder),
    )
    channels._databases.get(loop, {}).pop(key, None)
    channels._initialized_databases.get(loop, set()).discard(key)

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
    settings.lnbits_database_url = None
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
        await conn.execute(
            f"""CREATE TABLE {result_table_ref} (
                id TEXT PRIMARY KEY, scope_id TEXT NOT NULL,
                amount_msat BIGINT NOT NULL,
                __lnbits_owner_id__ TEXT NOT NULL,
                __lnbits_version__ BIGINT NOT NULL DEFAULT 1,
                __lnbits_immutable__ BOOLEAN NOT NULL DEFAULT false
            )"""
        )
        await conn.execute(
            f"""INSERT INTO {rooms} (room_id, owner_id, lease_owner)
                VALUES ('room', 'owner', 'lease')"""  # noqa: S608
        )

    await channels._save_room_state(
        database,
        extension_id,
        "room",
        "owner",
        "lease",
        sequence=3,
        snapshot={
            "round": 5,
            "result": {"scope_id": "room", "amount_msat": 7000},
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
                "result": {"scope_id": "room", "amount_msat": 8000},
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


@pytest.mark.anyio
async def test_stale_authoritative_rooms_and_client_sequences_are_reaped(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"cleanup{uuid4().hex[:8]}"
    database = await channels._database(extension_id)
    rooms = channels._table_ref(database, channels._ROOMS_TABLE)
    clients = channels._table_ref(database, channels._CLIENTS_TABLE)
    old_ms = int(time.time() * 1000) - channels._ROOM_RETENTION_MS - 1000
    async with database.connect() as conn:
        await conn.execute(
            f"""INSERT INTO {rooms}
                (room_id, owner_id, last_activity_ms) VALUES ('old', 'owner', :old)""",  # noqa: S608
            {"old": old_ms},
        )
        await conn.execute(
            f"""INSERT INTO {clients}
                (room_id, principal_id, last_client_sequence)
                VALUES ('old', 'principal', 4)"""  # noqa: S608
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
    await channels.release_authoritative_job(extension_id, "job")


@pytest.mark.anyio
async def test_authoritative_events_commit_snapshots_and_client_sequences(
    tmp_path: Path, settings: Settings, mocker
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"events{uuid4().hex[:8]}"
    channel = WasmAuthoritativeChannelConfig(
        authorizeConnection="authorize",
        onEvent="handle_event",
        ownerContext={"table": "rooms", "idParam": "id"},
        eventFields=["move"],
        maxEventsPerSecond=10,
        maxQueueDepth=4,
        maxActiveRooms=2,
    )
    extension = SimpleNamespace(
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
        assert await channels.get_authoritative_principal_sequence(
            extension_id, "room-1", "principal-1"
        ) == 1
    finally:
        entry = channels._channel_queues.pop(key, None)
        if entry:
            entry.worker.cancel()
            await asyncio.gather(entry.worker, return_exceptions=True)
