# ruff: noqa: S608
# Table identifiers are fixed constants and validated in `_table_ref`.

from __future__ import annotations

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import text

from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.core.wasm_ext.storage.crud import (
    _initialize_database_once,
    storage_insert_immutable_row,
)
from lnbits.db import SQLITE, Database

if TYPE_CHECKING:
    from lnbits.core.wasm_ext.wasm.config import WasmAuthoritativeChannelConfig
    from lnbits.core.wasm_ext.wasm.loader import WasmExtension

_ROOMS_TABLE = "lnbits_authoritative_rooms"
_CLIENTS_TABLE = "lnbits_authoritative_room_clients"
_CONNECTIONS_TABLE = "lnbits_authoritative_connections"
_JOBS_TABLE = "lnbits_authoritative_jobs_v2"
_ORDER_TABLE = "lnbits_authoritative_room_order"
_CAPACITY_TABLE = "lnbits_authoritative_capacity"
_ROOM_IDLE_SECONDS = 2
_ROOM_RETENTION_MS = 24 * 60 * 60 * 1000
_CAPACITY_RESERVATION_MS = 10 * 60 * 1000
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AuthoritativeChannelBackpressureError(ValueError):
    pass


class AuthoritativeChannelLeaseError(TimeoutError):
    pass


@dataclass(frozen=True)
class AuthoritativeChannelState:
    sequence: int
    version: int
    last_schedule_ms: int
    snapshot: Any
    has_snapshot: bool
    event_timestamps: list[int]


@dataclass
class _ChannelJob:
    extension: WasmExtension
    room_id: str
    owner_id: str
    export_name: str
    action: str
    payload: dict[str, Any]
    limits: dict[str, int]
    invoke_options: dict[str, Any]
    future: asyncio.Future[dict[str, Any]]
    admission_id: str
    admission_sequence: int
    principal_id: str | None = None
    client_sequence: int | None = None
    connection_id: str | None = None
    received_at_ns: int | None = None


@dataclass
class _ChannelQueue:
    queue: asyncio.Queue[_ChannelJob]
    worker: asyncio.Task[None]


_channel_queues: dict[tuple[str, str], _ChannelQueue] = {}


def validate_authoritative_channel_limits(
    channel: WasmAuthoritativeChannelConfig,
    limits: dict[str, int],
) -> None:
    if limits["wasm_runtime_max_execution_ms"] <= 0:
        raise ValueError("Authoritative WASM calls require a bounded execution time.")
    if channel.max_active_rooms > limits["wasm_runtime_max_authoritative_rooms"]:
        raise ValueError("Authoritative channel room limit exceeds the host ceiling.")
    if channel.max_queue_depth > limits["wasm_runtime_max_authoritative_queue_depth"]:
        raise ValueError("Authoritative channel queue limit exceeds the host ceiling.")
    if (
        channel.max_events_per_second
        > limits["wasm_runtime_max_authoritative_events_per_second"]
    ):
        raise ValueError("Authoritative channel event rate exceeds the host ceiling.")
    if channel.schedule_interval_ms is not None:
        maximum_schedule_rate = limits[
            "wasm_runtime_max_authoritative_schedule_rate_hz"
        ]
        minimum_schedule_interval_ms = (
            1000 + maximum_schedule_rate - 1
        ) // maximum_schedule_rate
        if channel.schedule_interval_ms < minimum_schedule_interval_ms:
            raise ValueError(
                "Authoritative channel schedule rate exceeds the host ceiling."
            )


async def run_authoritative_channel_export(
    extension: WasmExtension,
    room_id: str,
    owner_id: str,
    export_name: str,
    payload: dict[str, Any],
    *,
    limits: dict[str, int],
    action: str,
    invoke_options: dict[str, Any] | None = None,
    principal_id: str | None = None,
    client_sequence: int | None = None,
    connection_id: str | None = None,
    received_at_ns: int | None = None,
) -> dict[str, Any]:
    channel = extension.config.authoritative_channel
    if not channel:
        raise PermissionError("Authoritative channel dispatch is not enabled.")
    validate_authoritative_channel_limits(channel, limits)
    expected_exports = {"authorize": channel.authorize_connection}
    if channel.on_event:
        expected_exports["event"] = channel.on_event
    if channel.on_schedule:
        expected_exports["schedule"] = channel.on_schedule
    if action in {"authorize", "event", "schedule"} and (
        expected_exports.get(action) != export_name
    ):
        raise PermissionError("WASM export is not declared for this channel action.")
    if action not in {"authorize", "event", "schedule", "api"}:
        raise ValueError("Unknown authoritative room action.")

    admission_id = uuid4().hex
    admission_sequence = await reserve_authoritative_job(
        extension.id,
        room_id,
        admission_id,
        max_active_rooms=channel.max_active_rooms,
        max_queue_depth=channel.max_queue_depth,
        reservation_ms=max(
            _CAPACITY_RESERVATION_MS,
            limits["wasm_runtime_max_execution_ms"] * (channel.max_queue_depth + 2) * 2,
        ),
    )
    if admission_sequence is None:
        raise AuthoritativeChannelBackpressureError(
            "Authoritative channel room or event queue is full."
        )

    key = (extension.id, room_id)
    entry = _channel_queues.get(key)
    if entry is None:
        room_queue: asyncio.Queue[_ChannelJob] = asyncio.Queue(
            maxsize=channel.max_queue_depth
        )
        worker = asyncio.create_task(_run_channel_queue(key, room_queue))
        entry = _ChannelQueue(queue=room_queue, worker=worker)
        _channel_queues[key] = entry

    future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
    job = _ChannelJob(
        extension=extension,
        room_id=room_id,
        owner_id=owner_id,
        export_name=export_name,
        action=action,
        payload=payload,
        limits=limits,
        invoke_options=invoke_options or {},
        future=future,
        admission_id=admission_id,
        admission_sequence=admission_sequence,
        principal_id=principal_id,
        client_sequence=client_sequence,
        connection_id=connection_id,
        received_at_ns=received_at_ns,
    )
    try:
        entry.queue.put_nowait(job)
    except asyncio.QueueFull as exc:
        await release_authoritative_job(extension.id, admission_id)
        raise AuthoritativeChannelBackpressureError(
            "Authoritative channel event queue is full."
        ) from exc
    try:
        return await future
    except BaseException:
        # A cancelled caller would otherwise leave its reservation behind until
        # it expires, blocking every later action for this room.
        future.cancel()
        await asyncio.shield(release_authoritative_job(extension.id, admission_id))
        raise


async def get_authoritative_channel_state(
    extension_id: str,
    room_id: str,
    owner_id: str,
    *,
    max_bytes: int | None = None,
) -> AuthoritativeChannelState:
    database = await _database(extension_id)
    async with database.connect() as conn:
        row = await _raw_fetchone(
            conn,
            f"""SELECT sequence, version, last_schedule_ms, snapshot_json,
                    event_timestamps_json
                FROM {_table_ref(database, _ROOMS_TABLE)}
                WHERE room_id = :room_id AND owner_id = :owner_id""",
            {"room_id": room_id, "owner_id": owner_id},
        )
    if not row:
        raise PermissionError("Authoritative channel room was not found.")
    return _room_state(row, max_bytes=max_bytes)


async def get_authoritative_principal_sequence(
    extension_id: str,
    room_id: str,
    principal_id: str,
) -> int:
    database = await _database(extension_id)
    async with database.connect() as conn:
        row = await _raw_fetchone(
            conn,
            f"""SELECT last_client_sequence
                FROM {_table_ref(database, _CLIENTS_TABLE)}
                WHERE room_id = :room_id AND principal_id = :principal_id""",
            {"room_id": room_id, "principal_id": principal_id},
        )
    return int(row["last_client_sequence"]) if row else 0


async def reserve_authoritative_connection(
    extension_id: str,
    room_id: str,
    owner_id: str,
    connection_id: str,
    *,
    max_active_rooms: int,
    max_connections_per_room: int,
) -> bool:
    database = await _database(extension_id)
    now_ms = int(time.time() * 1000)
    connections = _table_ref(database, _CONNECTIONS_TABLE)
    rooms = _table_ref(database, _ROOMS_TABLE)
    async with database.connect() as conn:
        async with _transaction(conn):
            await _lock_capacity(conn, database)
            await _cleanup_capacity(conn, database, now_ms)
            room = await _raw_fetchone(
                conn,
                f"SELECT owner_id FROM {rooms} WHERE room_id = :room_id",
                {"room_id": room_id},
            )
            if room and room["owner_id"] != owner_id:
                raise PermissionError(
                    "Authoritative channel room owner does not match."
                )
            counts = await _capacity_counts(conn, database, room_id)
            if (
                not counts["room_active"] and counts["active_rooms"] >= max_active_rooms
            ) or counts["connections"] >= max_connections_per_room:
                return False
            await conn.conn.execute(
                text(f"""INSERT INTO {connections}
                    (connection_id, room_id, expires_at_ms)
                    VALUES (:connection_id, :room_id, :expires_at_ms)"""),
                {
                    "connection_id": connection_id,
                    "room_id": room_id,
                    "expires_at_ms": now_ms + _CAPACITY_RESERVATION_MS,
                },
            )
            return True


async def renew_authoritative_connection(
    extension_id: str, room_id: str, connection_id: str
) -> bool:
    database = await _database(extension_id)
    now_ms = int(time.time() * 1000)
    async with database.connect() as conn:
        result = await conn.execute(
            f"""UPDATE {_table_ref(database, _CONNECTIONS_TABLE)}
                SET expires_at_ms = :expires_at_ms
                WHERE connection_id = :connection_id AND room_id = :room_id""",
            {
                "expires_at_ms": now_ms + _CAPACITY_RESERVATION_MS,
                "connection_id": connection_id,
                "room_id": room_id,
            },
        )
        if result.rowcount:
            await conn.execute(
                f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                    SET last_activity_ms = :now_ms WHERE room_id = :room_id""",
                {"now_ms": now_ms, "room_id": room_id},
            )
        return bool(result.rowcount)


async def release_authoritative_connection(
    extension_id: str, connection_id: str
) -> None:
    database = await _database(extension_id)
    async with database.connect() as conn:
        await conn.execute(
            f"DELETE FROM {_table_ref(database, _CONNECTIONS_TABLE)} "
            "WHERE connection_id = :connection_id",
            {"connection_id": connection_id},
        )


async def reserve_authoritative_job(
    extension_id: str,
    room_id: str,
    job_id: str,
    *,
    max_active_rooms: int,
    max_queue_depth: int,
    reservation_ms: int = _CAPACITY_RESERVATION_MS,
) -> int | None:
    database = await _database(extension_id)
    now_ms = int(time.time() * 1000)
    jobs = _table_ref(database, _JOBS_TABLE)
    async with database.connect() as conn:
        async with _transaction(conn):
            await _lock_capacity(conn, database)
            await _cleanup_capacity(conn, database, now_ms)
            counts = await _capacity_counts(conn, database, room_id)
            if (
                not counts["room_active"] and counts["active_rooms"] >= max_active_rooms
            ) or counts["jobs"] >= max_queue_depth + 1:
                return None
            order = _table_ref(database, _ORDER_TABLE)
            sequence_row = await _raw_fetchone(
                conn,
                f"SELECT next_sequence FROM {order} WHERE room_id = :room_id",
                {"room_id": room_id},
            )
            admission_sequence = (
                int(sequence_row["next_sequence"]) + 1 if sequence_row else 1
            )
            await conn.conn.execute(
                text(f"""INSERT INTO {order} (room_id, next_sequence)
                    VALUES (:room_id, :sequence)
                    ON CONFLICT (room_id) DO UPDATE
                    SET next_sequence = :sequence"""),
                {"room_id": room_id, "sequence": admission_sequence},
            )
            await conn.conn.execute(
                text(f"""INSERT INTO {jobs}
                    (job_id, room_id, admission_sequence, expires_at_ms)
                    VALUES (:job_id, :room_id, :sequence, :expires_at_ms)"""),
                {
                    "job_id": job_id,
                    "room_id": room_id,
                    "sequence": admission_sequence,
                    "expires_at_ms": now_ms + reservation_ms,
                },
            )
            return admission_sequence


async def release_authoritative_job(extension_id: str, job_id: str) -> None:
    database = await _database(extension_id)
    async with database.connect() as conn:
        await conn.execute(
            f"DELETE FROM {_table_ref(database, _JOBS_TABLE)} "
            "WHERE job_id = :job_id",
            {"job_id": job_id},
        )


async def _lock_capacity(conn: Any, database: Database) -> None:
    # ponytail: global lock; per-room locks if reservation throughput matters.
    if database.type == SQLITE:
        # SQLite has no row-level FOR UPDATE; take its write lock before reading.
        capacity = _table_ref(database, _CAPACITY_TABLE)
        await conn.conn.execute(text(f"UPDATE {capacity} SET id = id WHERE id = 1"))
        return
    await _raw_fetchone(
        conn,
        f"SELECT id FROM {_table_ref(database, _CAPACITY_TABLE)} "
        f"WHERE id = 1{_for_update(conn.type)}",
        {},
    )


async def _capacity_counts(
    conn: Any, database: Database, room_id: str
) -> dict[str, Any]:
    connections = _table_ref(database, _CONNECTIONS_TABLE)
    jobs = _table_ref(database, _JOBS_TABLE)
    row = await _raw_fetchone(
        conn,
        f"""SELECT
            (SELECT COUNT(DISTINCT room_id) FROM (
                SELECT room_id FROM {connections}
                UNION SELECT room_id FROM {jobs}
            ) active) AS active_rooms,
            (SELECT COUNT(*) FROM {connections} WHERE room_id = :room_id)
                AS connections,
            (SELECT COUNT(*) FROM {jobs} WHERE room_id = :room_id) AS jobs,
            (SELECT COUNT(*) FROM (
                SELECT room_id FROM {connections} WHERE room_id = :room_id
                UNION SELECT room_id FROM {jobs} WHERE room_id = :room_id
            ) active_room) AS room_active""",
        {"room_id": room_id},
    )
    return {key: int(value) for key, value in row.items()}


async def _cleanup_capacity(conn: Any, database: Database, now_ms: int) -> None:
    connections = _table_ref(database, _CONNECTIONS_TABLE)
    jobs = _table_ref(database, _JOBS_TABLE)
    rooms = _table_ref(database, _ROOMS_TABLE)
    clients = _table_ref(database, _CLIENTS_TABLE)
    order = _table_ref(database, _ORDER_TABLE)
    await conn.conn.execute(
        text(f"DELETE FROM {connections} WHERE expires_at_ms <= :now_ms"),
        {"now_ms": now_ms},
    )
    await conn.conn.execute(
        text(f"DELETE FROM {jobs} WHERE expires_at_ms <= :now_ms"),
        {"now_ms": now_ms},
    )
    stale = f"""SELECT room_id FROM {rooms}
        WHERE last_activity_ms < :cutoff_ms AND lease_until_ms <= :now_ms
        AND room_id NOT IN (SELECT room_id FROM {connections})
        AND room_id NOT IN (SELECT room_id FROM {jobs})"""
    await conn.conn.execute(
        text(f"DELETE FROM {clients} WHERE room_id IN ({stale})"),
        {"cutoff_ms": now_ms - _ROOM_RETENTION_MS, "now_ms": now_ms},
    )
    await conn.conn.execute(
        text(f"DELETE FROM {order} WHERE room_id IN ({stale})"),
        {"cutoff_ms": now_ms - _ROOM_RETENTION_MS, "now_ms": now_ms},
    )
    await conn.conn.execute(
        text(f"DELETE FROM {rooms} WHERE room_id IN ({stale})"),
        {"cutoff_ms": now_ms - _ROOM_RETENTION_MS, "now_ms": now_ms},
    )


async def _run_channel_queue(
    key: tuple[str, str],
    queue: asyncio.Queue[_ChannelJob],
) -> None:
    while True:
        try:
            job = await asyncio.wait_for(queue.get(), timeout=_ROOM_IDLE_SECONDS)
        except asyncio.TimeoutError:
            if queue.empty():
                entry = _channel_queues.get(key)
                if entry and entry.queue is queue:
                    _channel_queues.pop(key, None)
                return
            continue
        if job.future.cancelled():
            await release_authoritative_job(job.extension.id, job.admission_id)
            queue.task_done()
            continue
        try:
            result = await _execute_channel_job(job)
        except Exception as exc:
            if not job.future.done():
                job.future.set_exception(exc)
        else:
            if not job.future.done():
                job.future.set_result(result)
        finally:
            await release_authoritative_job(job.extension.id, job.admission_id)
            queue.task_done()


async def _execute_channel_job(job: _ChannelJob) -> dict[str, Any]:
    channel = job.extension.config.authoritative_channel
    if not channel:
        raise PermissionError("Authoritative channel dispatch is not enabled.")
    database = await _database(job.extension.id)
    lease_ms = max(
        10_000,
        job.limits["wasm_runtime_max_execution_ms"] * 3 + 5_000,
    )
    await _wait_for_job_turn(database, job)
    async with _room_lease(database, job.room_id, job.owner_id, lease_ms) as lease:
        state = await _read_room_state(
            database,
            job.room_id,
            job.owner_id,
            max_bytes=job.limits["wasm_runtime_max_authoritative_state_bytes"],
        )
        now_ms = int(time.time() * 1000)
        if job.action == "schedule":
            if channel.schedule_interval_ms is None:
                raise PermissionError("Channel scheduling is not configured.")
            if not await _claim_room_schedule(
                database, job, state, lease, now_ms, channel.schedule_interval_ms
            ):
                return {"_hostSkipped": True}
        if job.action == "event":
            await _check_room_event(database, job, state, lease, now_ms, channel)

        sequence = state.sequence + (0 if job.action == "authorize" else 1)
        result = await _invoke_room_job(job, sequence, state, now_ms)
        if _authoritative_job_rejected(job.action, result):
            raise PermissionError("Authoritative WASM channel rejected the action.")
        if job.action == "api" and isinstance(result, dict):
            if result.get("ok") is False:
                return result

        data = result.get("data")
        has_snapshot, snapshot = _returned_snapshot(
            job.action,
            data,
            state.has_snapshot,
            max_bytes=job.limits["wasm_runtime_max_authoritative_state_bytes"],
        )
        if job.action in {"event", "schedule"} and not has_snapshot:
            raise ValueError(
                "Authoritative channel handler must return a state snapshot."
            )
        await _save_room_state(
            database,
            job.extension.id,
            job.room_id,
            job.owner_id,
            lease,
            sequence=sequence,
            snapshot=snapshot,
            has_snapshot=has_snapshot,
            update_sequence=job.action != "authorize",
            principal_id=job.principal_id if job.action == "event" else None,
            client_sequence=(job.client_sequence if job.action == "event" else None),
            result_table=channel.result_table,
            result_field=channel.result_field,
        )
        return result


async def _wait_for_job_turn(database: Database, job: _ChannelJob) -> None:
    jobs = _table_ref(database, _JOBS_TABLE)
    deadline = time.monotonic() + max(
        10,
        job.limits["wasm_runtime_max_execution_ms"]
        * (job.extension.config.authoritative_channel.max_queue_depth + 2)
        / 1000
        * 3,
    )
    while time.monotonic() < deadline:
        now_ms = int(time.time() * 1000)
        async with database.connect() as conn:
            earlier = await _raw_fetchone(
                conn,
                f"""SELECT job_id FROM {jobs}
                    WHERE room_id = :room_id AND admission_sequence < :sequence
                        AND expires_at_ms > :now_ms
                    ORDER BY admission_sequence LIMIT 1""",
                {
                    "room_id": job.room_id,
                    "sequence": job.admission_sequence,
                    "now_ms": now_ms,
                },
            )
        if not earlier:
            return
        await asyncio.sleep(0.01)
    raise AuthoritativeChannelLeaseError(
        "Authoritative channel input is waiting behind an earlier room action."
    )


async def _claim_room_schedule(
    database: Database,
    job: _ChannelJob,
    state: AuthoritativeChannelState,
    lease: str,
    now_ms: int,
    schedule_interval_ms: int,
) -> bool:
    if now_ms - state.last_schedule_ms < schedule_interval_ms:
        return False
    await _set_last_schedule(database, job.room_id, lease, now_ms)
    return True


async def _check_room_event(
    database: Database,
    job: _ChannelJob,
    state: AuthoritativeChannelState,
    lease: str,
    now_ms: int,
    channel: WasmAuthoritativeChannelConfig,
) -> None:
    if not job.principal_id or job.client_sequence is None:
        raise ValueError("Authoritative event identity is incomplete.")
    last_sequence = await get_authoritative_principal_sequence(
        job.extension.id, job.room_id, job.principal_id
    )
    if job.client_sequence <= last_sequence:
        raise ValueError("Authoritative event sequence is stale.")
    event_timestamps = [
        timestamp for timestamp in state.event_timestamps if now_ms - timestamp < 1000
    ]
    if len(event_timestamps) >= channel.max_events_per_second:
        raise ValueError("Authoritative channel event rate exceeded.")
    event_timestamps.append(now_ms)
    await _set_event_timestamps(database, job.room_id, lease, event_timestamps)


def _authoritative_job_rejected(action: str, result: Any) -> bool:
    return action in {"event", "schedule", "authorize"} and (
        not isinstance(result, dict) or result.get("ok") is not True
    )


async def _invoke_room_job(
    job: _ChannelJob,
    sequence: int,
    state: AuthoritativeChannelState,
    now_ms: int,
) -> dict[str, Any]:
    from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export

    trigger_types = {
        "authorize": "websocket_authorize",
        "event": "websocket_event",
        "schedule": "websocket_schedule",
        "api": "http",
    }
    return await invoke_wasm_extension_export(
        job.extension.id,
        job.export_name,
        _invocation_payload(job, sequence, state, now_ms),
        owner_id=job.owner_id,
        trigger_type=trigger_types[job.action],
        context="event",
        authoritative_execution=True,
        **job.invoke_options,
    )


def _invocation_payload(
    job: _ChannelJob,
    sequence: int,
    state: AuthoritativeChannelState,
    now_ms: int,
) -> dict[str, Any]:
    context = {
        "extensionId": job.extension.id,
        "roomId": job.room_id,
        "sequence": sequence,
        "serverTimeMs": now_ms,
        "state": state.snapshot,
    }
    if job.action == "event":
        return {
            "extensionId": job.extension.id,
            "roomId": job.room_id,
            "principalId": job.principal_id,
            "principalRole": job.payload.get("principalRole"),
            "connectionId": job.connection_id,
            "sequence": sequence,
            "clientSequence": job.client_sequence,
            "receivedAtNs": job.received_at_ns,
            "event": job.payload["event"],
            "serverTimeMs": now_ms,
            "state": state.snapshot,
        }
    if job.action == "schedule":
        return context
    return {**job.payload, "_authoritative": context}


def _returned_snapshot(
    action: str,
    data: Any,
    current_exists: bool,
    *,
    max_bytes: int,
) -> tuple[bool, Any]:
    if not isinstance(data, dict):
        if action in {"event", "schedule"}:
            raise ValueError("Authoritative channel export response is invalid.")
        return False, None
    if action == "authorize" and current_exists:
        return False, None
    if "state" in data:
        value = data["state"]
    elif "snapshot" in data:
        value = data["snapshot"]
    else:
        return False, None
    if len(json.dumps(value, allow_nan=False).encode()) > max_bytes:
        raise ValueError("Authoritative channel snapshot exceeds the host size limit.")
    return True, value


def _strict_json_loads(value: str) -> Any:
    def reject_constant(constant: str) -> None:
        raise ValueError(f"Invalid JSON constant: {constant}")

    return json.loads(value, parse_constant=reject_constant)


async def _database(extension_id: str) -> Database:
    await _initialize_database_once(
        extension_id, "authoritative", _create_authoritative_tables
    )
    return storage_crud._database(extension_id)


async def _create_authoritative_tables(database: Database) -> None:
    rooms = _table_ref(database, _ROOMS_TABLE)
    clients = _table_ref(database, _CLIENTS_TABLE)
    connections = _table_ref(database, _CONNECTIONS_TABLE)
    jobs = _table_ref(database, _JOBS_TABLE)
    capacity = _table_ref(database, _CAPACITY_TABLE)
    order = _table_ref(database, _ORDER_TABLE)
    async with database.connect() as conn:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {rooms} (
                room_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                sequence {database.big_int} NOT NULL DEFAULT 0,
                version {database.big_int} NOT NULL DEFAULT 0,
                snapshot_json TEXT,
                event_timestamps_json TEXT NOT NULL DEFAULT '[]',
                last_schedule_ms {database.big_int} NOT NULL DEFAULT 0,
                last_activity_ms {database.big_int} NOT NULL DEFAULT 0,
                lease_owner TEXT,
                lease_until_ms {database.big_int} NOT NULL DEFAULT 0
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {clients} (
                room_id TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                last_client_sequence {database.big_int} NOT NULL DEFAULT 0,
                PRIMARY KEY (room_id, principal_id)
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {capacity} (
                id INTEGER PRIMARY KEY
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {connections} (
                connection_id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                expires_at_ms {database.big_int} NOT NULL
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {jobs} (
                job_id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                admission_sequence {database.big_int} NOT NULL,
                expires_at_ms {database.big_int} NOT NULL
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {order} (
                room_id TEXT PRIMARY KEY,
                next_sequence {database.big_int} NOT NULL
            )
        """)
        await conn.execute(f"""
            INSERT INTO {capacity} (id) VALUES (1)
            ON CONFLICT (id) DO NOTHING
        """)


@asynccontextmanager
async def _room_lease(
    database: Database,
    room_id: str,
    owner_id: str,
    lease_ms: int,
):
    await _ensure_room(database, room_id, owner_id)
    lease = uuid4().hex
    acquired_at = int(time.time() * 1000)
    acquired = False
    async with database.connect() as conn:
        async with _transaction(conn):
            result = await conn.conn.execute(
                text(f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                    SET lease_owner = :lease, lease_until_ms = :lease_until
                    WHERE room_id = :room_id AND owner_id = :owner_id
                    AND (lease_owner IS NULL OR lease_until_ms <= :now_ms)"""),
                {
                    "lease": lease,
                    "lease_until": acquired_at + lease_ms,
                    "room_id": room_id,
                    "owner_id": owner_id,
                    "now_ms": acquired_at,
                },
            )
            acquired = bool(result.rowcount)
            result.close()
    if not acquired:
        end = time.monotonic() + max(5, lease_ms / 1000)
        while time.monotonic() < end:
            await asyncio.sleep(0.025)
            acquired_at = int(time.time() * 1000)
            async with database.connect() as conn:
                async with _transaction(conn):
                    result = await conn.conn.execute(
                        text(f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                            SET lease_owner = :lease, lease_until_ms = :lease_until
                            WHERE room_id = :room_id AND owner_id = :owner_id
                            AND (lease_owner IS NULL OR lease_until_ms <= :now_ms)"""),
                        {
                            "lease": lease,
                            "lease_until": acquired_at + lease_ms,
                            "room_id": room_id,
                            "owner_id": owner_id,
                            "now_ms": acquired_at,
                        },
                    )
                    acquired = bool(result.rowcount)
                    result.close()
            if acquired:
                break
    if not acquired:
        raise AuthoritativeChannelLeaseError(
            "Authoritative channel room is busy; retry the action."
        )

    stop_renewal = asyncio.Event()
    renewal = asyncio.create_task(
        _renew_room_lease(database, room_id, lease, lease_ms, stop_renewal)
    )
    try:
        yield lease
    finally:
        stop_renewal.set()
        await renewal
        await _release_room_lease(database, room_id, lease)


async def _renew_room_lease(
    database: Database,
    room_id: str,
    lease: str,
    lease_ms: int,
    stop: asyncio.Event,
) -> None:
    interval = max(1, lease_ms // 3000) / 1000
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            pass
        now_ms = int(time.time() * 1000)
        async with database.connect() as conn:
            result = await conn.execute(
                f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                    SET lease_until_ms = :lease_until, last_activity_ms = :now_ms
                    WHERE room_id = :room_id AND lease_owner = :lease""",
                {
                    "lease_until": now_ms + lease_ms,
                    "now_ms": now_ms,
                    "room_id": room_id,
                    "lease": lease,
                },
            )
            if not result.rowcount:
                return


async def _release_room_lease(
    database: Database,
    room_id: str,
    lease: str,
) -> None:
    async with database.connect() as conn:
        await conn.execute(
            f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                SET lease_owner = NULL, lease_until_ms = 0
                WHERE room_id = :room_id AND lease_owner = :lease""",
            {"room_id": room_id, "lease": lease},
        )


async def _ensure_room(database: Database, room_id: str, owner_id: str) -> None:
    table = _table_ref(database, _ROOMS_TABLE)
    async with database.connect() as conn:
        async with _transaction(conn):
            now_ms = int(time.time() * 1000)
            await conn.conn.execute(
                text(f"""INSERT INTO {table}
                    (room_id, owner_id, last_activity_ms)
                    VALUES (:room_id, :owner_id, :now_ms)
                    ON CONFLICT (room_id) DO NOTHING"""),
                {"room_id": room_id, "owner_id": owner_id, "now_ms": now_ms},
            )
            row = await _raw_fetchone(
                conn,
                f"SELECT owner_id FROM {table} WHERE room_id = :room_id",
                {"room_id": room_id},
            )
    if not row or row["owner_id"] != owner_id:
        raise PermissionError("Authoritative channel room owner does not match.")


async def _read_room_state(
    database: Database,
    room_id: str,
    owner_id: str,
    *,
    max_bytes: int,
) -> AuthoritativeChannelState:
    async with database.connect() as conn:
        row = await _raw_fetchone(
            conn,
            f"""SELECT sequence, version, last_schedule_ms, snapshot_json,
                    event_timestamps_json
                FROM {_table_ref(database, _ROOMS_TABLE)}
                WHERE room_id = :room_id AND owner_id = :owner_id""",
            {"room_id": room_id, "owner_id": owner_id},
        )
    if not row:
        raise PermissionError("Authoritative channel room was not found.")
    return _room_state(row, max_bytes=max_bytes)


def _room_state(
    row: Any,
    *,
    max_bytes: int | None = None,
) -> AuthoritativeChannelState:
    raw_snapshot = row["snapshot_json"]
    event_timestamps = _strict_json_loads(row["event_timestamps_json"] or "[]")
    has_snapshot = raw_snapshot is not None
    snapshot = _strict_json_loads(raw_snapshot) if has_snapshot else None
    if max_bytes is not None and has_snapshot:
        if len(json.dumps(snapshot, allow_nan=False).encode()) > max_bytes:
            raise ValueError(
                "Stored authoritative channel snapshot exceeds the host limit."
            )
    if not isinstance(event_timestamps, list) or not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in event_timestamps
    ):
        raise ValueError("Stored authoritative channel event rate state is invalid.")
    return AuthoritativeChannelState(
        sequence=int(row["sequence"]),
        version=int(row["version"]),
        last_schedule_ms=int(row["last_schedule_ms"]),
        snapshot=snapshot,
        has_snapshot=has_snapshot,
        event_timestamps=event_timestamps,
    )


async def _set_last_schedule(
    database: Database,
    room_id: str,
    lease: str,
    now_ms: int,
) -> None:
    async with database.connect() as conn:
        await conn.execute(
            f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                SET last_schedule_ms = :now_ms, last_activity_ms = :now_ms
                WHERE room_id = :room_id AND lease_owner = :lease""",
            {"now_ms": now_ms, "room_id": room_id, "lease": lease},
        )


async def _set_event_timestamps(
    database: Database,
    room_id: str,
    lease: str,
    timestamps: list[int],
) -> None:
    async with database.connect() as conn:
        await conn.execute(
            f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                SET event_timestamps_json = :timestamps
                WHERE room_id = :room_id AND lease_owner = :lease""",
            {
                "timestamps": json.dumps(timestamps),
                "room_id": room_id,
                "lease": lease,
            },
        )


async def _save_room_state(
    database: Database,
    extension_id: str,
    room_id: str,
    owner_id: str,
    lease: str,
    *,
    sequence: int,
    snapshot: Any,
    has_snapshot: bool,
    update_sequence: bool,
    principal_id: str | None,
    client_sequence: int | None,
    result_table: str | None = None,
    result_field: str = "result",
) -> None:
    now_ms = int(time.time() * 1000)
    async with database.connect() as conn:
        async with _transaction(conn):
            if result_table and has_snapshot and isinstance(snapshot, dict):
                result_data = snapshot.get(result_field)
                if result_data is not None:
                    if not isinstance(result_data, dict):
                        raise ValueError("Authoritative result must be an object.")
                    await storage_insert_immutable_row(
                        conn,
                        extension_id,
                        result_table,
                        {**result_data, "id": room_id},
                        owner_id,
                    )
            current = await _raw_fetchone(
                conn,
                f"""SELECT version, lease_owner
                    FROM {_table_ref(database, _ROOMS_TABLE)}
                    WHERE room_id = :room_id AND owner_id = :owner_id""",
                {"room_id": room_id, "owner_id": owner_id},
            )
            if not current or current["lease_owner"] != lease:
                raise AuthoritativeChannelLeaseError(
                    "Authoritative channel room lease was lost."
                )
            snapshot_json = (
                json.dumps(snapshot, allow_nan=False) if has_snapshot else None
            )
            sequence_update = sequence if update_sequence else None
            result = await conn.conn.execute(
                text(f"""UPDATE {_table_ref(database, _ROOMS_TABLE)}
                    SET sequence = COALESCE(:sequence, sequence),
                        version = version + :version_increment,
                        snapshot_json = COALESCE(:snapshot, snapshot_json),
                        last_activity_ms = :now_ms
                    WHERE room_id = :room_id AND owner_id = :owner_id
                        AND lease_owner = :lease"""),
                {
                    "sequence": sequence_update,
                    "version_increment": int(has_snapshot),
                    "snapshot": snapshot_json,
                    "now_ms": now_ms,
                    "room_id": room_id,
                    "owner_id": owner_id,
                    "lease": lease,
                },
            )
            if not result.rowcount:
                raise AuthoritativeChannelLeaseError(
                    "Authoritative channel room lease was lost."
                )
            result.close()
            if principal_id and client_sequence is not None:
                await conn.conn.execute(
                    text(f"""INSERT INTO {_table_ref(database, _CLIENTS_TABLE)}
                        (room_id, principal_id, last_client_sequence)
                        VALUES (:room_id, :principal_id, :sequence)
                        ON CONFLICT (room_id, principal_id) DO UPDATE
                        SET last_client_sequence = excluded.last_client_sequence"""),
                    {
                        "room_id": room_id,
                        "principal_id": principal_id,
                        "sequence": client_sequence,
                    },
                )


async def _raw_fetchone(conn: Any, query: str, values: dict[str, Any]) -> Any:
    result = await conn.conn.execute(text(query), values)
    row = result.mappings().first()
    result.close()
    return row


@asynccontextmanager
async def _transaction(conn: Any):
    if conn.type != SQLITE:
        async with conn.conn.begin():
            yield
        return
    # SQLite attaches the extension file under its schema alias; BEGIN IMMEDIATE
    # locks the same file twice, so let the first write acquire the DB lock.
    await conn.conn.exec_driver_sql("BEGIN")
    try:
        yield
    except BaseException:
        await conn.conn.rollback()
        raise
    else:
        await conn.conn.commit()


def _table_ref(database: Database, name: str) -> str:
    if not _SQL_IDENTIFIER_RE.fullmatch(name):
        raise ValueError("Invalid authoritative channel table name.")
    if not database.schema:
        return name
    if not _SQL_IDENTIFIER_RE.fullmatch(database.schema):
        raise ValueError("Invalid authoritative channel database schema.")
    return f"{database.schema}.{name}"


def _for_update(database_type: str) -> str:
    return " FOR UPDATE" if database_type != SQLITE else ""
