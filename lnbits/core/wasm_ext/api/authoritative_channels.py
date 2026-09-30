# ruff: noqa: S608
# Table identifiers are fixed constants and validated in `_table_ref`.

from __future__ import annotations

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from loguru import logger
from sqlalchemy import text

from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.core.wasm_ext.storage.crud import (
    _initialize_database_once,
    storage_insert_immutable_row,
)
from lnbits.db import SQLITE, Database
from lnbits.settings import settings

from . import ephemeral_broker as broker

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
_EPHEMERAL_CONNECTION_MS = 30_000
_MAX_EPHEMERAL_PRINCIPALS_PER_ROOM = 1024
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AuthoritativeChannelBackpressureError(ValueError):
    pass


class AuthoritativeChannelLeaseError(TimeoutError):
    pass


class AuthoritativeChannelRejectedError(PermissionError):
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
    persistence: str = "durable"
    room_generation: str | None = None
    actor_generation: str | None = None
    permissions: list[Any] | None = None
    policy_generation: int | None = None
    execution_sequence: int | None = None


@dataclass
class _ChannelQueue:
    queue: asyncio.Queue[_ChannelJob]
    worker: asyncio.Task[None]


@dataclass
class _EphemeralRoom:
    owner_id: str
    generation: str
    state: AuthoritativeChannelState
    last_activity_ms: int
    principal_sequences: dict[str, int] = field(default_factory=dict)
    connections: dict[str, int] = field(default_factory=dict)
    pending_jobs: int = 0
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    scheduler_task: asyncio.Task[None] | None = None


_channel_queues: dict[tuple[str, str], _ChannelQueue] = {}
_ephemeral_rooms: dict[tuple[str, str], _EphemeralRoom] = {}
_ephemeral_extension_generations: dict[str, int] = {}
_broker_epochs: dict[str, int] = {}
_broker_extensions: dict[str, Any] = {}
_remote_generations: dict[tuple[str, str, str], str] = {}
_remote_connection_rooms: dict[tuple[str, str], tuple[str, str, str]] = {}


def get_ephemeral_authoritative_extension_generation(extension_id: str) -> int:
    return _ephemeral_extension_generations.get(extension_id, 0)


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


async def run_authoritative_channel_export(  # noqa: C901
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
    room_generation: str | None = None,
    permissions: list[Any] | None = None,
    policy_generation: int | None = None,
) -> dict[str, Any]:
    channel = extension.config.authoritative_channel
    if not channel:
        raise PermissionError("Authoritative channel dispatch is not enabled.")
    validate_authoritative_channel_limits(channel, limits)
    persistence = getattr(channel, "persistence", "durable")
    if persistence == "ephemeral":
        if permissions is None:
            raise PermissionError("Ephemeral channel permissions are not authorized.")
        if policy_generation != get_ephemeral_authoritative_extension_generation(
            extension.id
        ):
            raise PermissionError("Ephemeral authoritative channel policy changed.")
        _broker_extensions[extension.id] = extension
        options = dict(invoke_options or {})
        options.pop("access_token", None)
        account = options.pop("user", None)
        if account is not None:
            options["broker_account_id"] = account.id
        routed = (
            await broker.call(
                extension.id,
                "export",
                {
                    "room_id": room_id,
                    "owner_id": owner_id,
                    "export_name": export_name,
                    "payload": payload,
                    "limits": limits,
                    "action": action,
                    "invoke_options": options,
                    "principal_id": principal_id,
                    "client_sequence": client_sequence,
                    "connection_id": connection_id,
                    "received_at_ns": received_at_ns,
                    "room_generation": room_generation,
                    "permissions": [
                        item.dict() if hasattr(item, "dict") else item
                        for item in (permissions or [])
                    ],
                    "policy_generation": policy_generation,
                },
            )
            if not broker.in_handler()
            else None
        )
        if routed is not None:
            return routed
        _check_actor_ownership(extension.id)
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
    actor_generation = None
    ephemeral_room = None
    admission_sequence: int | None
    if persistence == "ephemeral":
        if permissions is None:
            raise PermissionError("Ephemeral channel permissions are not authorized.")
        if policy_generation != get_ephemeral_authoritative_extension_generation(
            extension.id
        ):
            raise PermissionError("Ephemeral authoritative channel policy changed.")
        await _restore_ephemeral_room(
            extension.id, room_id, owner_id, channel.max_active_rooms
        )
        ephemeral_room = _get_ephemeral_room(
            extension.id,
            room_id,
            owner_id,
            max_active_rooms=channel.max_active_rooms,
            create=True,
        )
        if ephemeral_room.pending_jobs >= channel.max_queue_depth + 1:
            raise AuthoritativeChannelBackpressureError(
                "Authoritative channel room or event queue is full."
            )
        ephemeral_room.pending_jobs += 1
        ephemeral_room.last_activity_ms = int(time.time() * 1000)
        actor_generation = ephemeral_room.generation
        admission_sequence = ephemeral_room.state.sequence + ephemeral_room.pending_jobs
    else:
        admission_sequence = await reserve_authoritative_job(
            extension.id,
            room_id,
            admission_id,
            max_active_rooms=channel.max_active_rooms,
            max_queue_depth=channel.max_queue_depth,
            reservation_ms=max(
                _CAPACITY_RESERVATION_MS,
                limits["wasm_runtime_max_execution_ms"]
                * (channel.max_queue_depth + 2)
                * 2,
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
        persistence=persistence,
        room_generation=room_generation,
        actor_generation=actor_generation,
        permissions=permissions,
        policy_generation=policy_generation,
    )
    try:
        entry.queue.put_nowait(job)
    except asyncio.QueueFull as exc:
        await _release_channel_job(job)
        raise AuthoritativeChannelBackpressureError(
            "Authoritative channel event queue is full."
        ) from exc
    try:
        result = await future
        if action == "event":
            return {**result, "_hostSequence": job.execution_sequence}
        return result
    except BaseException:
        # The queue worker releases admission after handling or skipping this job.
        future.cancel()
        if job.persistence == "durable":
            await asyncio.shield(release_authoritative_job(extension.id, admission_id))
        raise


async def _restore_ephemeral_room(
    extension_id: str, room_id: str, owner_id: str, max_active_rooms: int
) -> None:
    key = (extension_id, room_id)
    if key in _ephemeral_rooms:
        return
    state = await broker.recover_state(extension_id, room_id, owner_id)
    # Another admission can initialize the room while this read is pending.
    if state is None or key in _ephemeral_rooms:
        return
    recovered = AuthoritativeChannelState(**state)
    room = _get_ephemeral_room(
        extension_id, room_id, owner_id, max_active_rooms=max_active_rooms, create=True
    )
    room.state = recovered
    # Connections and input high-water marks belong to the old generation.
    # Reconnecting callers receive a fresh generation and must reauthorize.
    broker.publish_state(
        extension_id,
        room_id,
        owner_id,
        asdict(recovered),
        room.generation,
        max_rooms=max_active_rooms,
    )


def _get_ephemeral_room(
    extension_id: str,
    room_id: str,
    owner_id: str,
    *,
    max_active_rooms: int,
    create: bool,
) -> _EphemeralRoom:
    now_ms = int(time.time() * 1000)
    key = (extension_id, room_id)
    room = _ephemeral_rooms.get(key)
    if room:
        if room.owner_id != owner_id:
            raise PermissionError("Authoritative channel room owner does not match.")
        _prune_ephemeral_connections(room, now_ms)
        return room
    if not create:
        raise PermissionError("Authoritative channel room was not found.")
    # Only the cold path (creating a room) needs the full sweep: it evicts
    # retention-expired rooms so the per-extension room count stays accurate.
    _prune_ephemeral_rooms(extension_id, now_ms)
    extension_rooms = [
        (extension_key, candidate)
        for extension_key, candidate in _ephemeral_rooms.items()
        if extension_key[0] == extension_id
    ]
    if len(extension_rooms) >= max_active_rooms:
        inactive_rooms = [
            (extension_key, candidate)
            for extension_key, candidate in extension_rooms
            if not candidate.connections and not candidate.pending_jobs
        ]
        if not inactive_rooms:
            raise AuthoritativeChannelBackpressureError(
                "Authoritative channel room limit is full."
            )
        # ponytail: retain at most max_active_rooms actors.
        # Use external persistence to scale idle-room retention.
        oldest_key, _ = min(inactive_rooms, key=lambda item: item[1].last_activity_ms)
        _discard_idle_ephemeral_room(oldest_key)
    state = AuthoritativeChannelState(
        sequence=0,
        version=0,
        last_schedule_ms=0,
        snapshot=None,
        has_snapshot=False,
        event_timestamps=[],
    )
    room = _EphemeralRoom(
        owner_id=owner_id,
        generation=uuid4().hex,
        state=state,
        last_activity_ms=now_ms,
    )
    _ephemeral_rooms[key] = room
    return room


def _prune_ephemeral_connections(room: _EphemeralRoom, now_ms: int) -> None:
    for connection, deadline in list(room.connections.items()):
        if deadline <= now_ms:
            room.connections.pop(connection, None)


def _prune_ephemeral_rooms(extension_id: str, now_ms: int) -> None:
    for key, candidate in list(_ephemeral_rooms.items()):
        _prune_ephemeral_connections(candidate, now_ms)
        if (
            key[0] == extension_id
            and not candidate.connections
            and not candidate.pending_jobs
            and now_ms - candidate.last_activity_ms > _ROOM_RETENTION_MS
        ):
            _discard_idle_ephemeral_room(key)


def _discard_idle_ephemeral_room(key: tuple[str, str]) -> None:
    room = _ephemeral_rooms.pop(key, None)
    if room:
        if room.scheduler_task and not room.scheduler_task.done():
            room.scheduler_task.cancel()
        room.changed.set()
    entry = _channel_queues.get(key)
    if entry and entry.queue.empty():
        _channel_queues.pop(key, None)
        entry.worker.cancel()


async def _release_channel_job(job: _ChannelJob) -> None:
    if job.persistence == "ephemeral":
        room = _ephemeral_rooms.get((job.extension.id, job.room_id))
        if room and room.generation == job.actor_generation:
            room.pending_jobs = max(0, room.pending_jobs - 1)
            room.last_activity_ms = int(time.time() * 1000)
            if (
                not room.connections
                and not room.pending_jobs
                and not room.state.has_snapshot
            ):
                _ephemeral_rooms.pop((job.extension.id, job.room_id), None)
        return
    await release_authoritative_job(job.extension.id, job.admission_id)


def invalidate_ephemeral_authoritative_extension(  # noqa: C901
    extension_id: str,
) -> None:
    _broker_extensions.pop(extension_id, None)
    for remote_key in list(_remote_generations):
        if remote_key[0] == extension_id:
            _remote_generations.pop(remote_key, None)
    for connection_key in list(_remote_connection_rooms):
        if connection_key[0] == extension_id:
            _remote_connection_rooms.pop(connection_key, None)
    _ephemeral_extension_generations[extension_id] = (
        get_ephemeral_authoritative_extension_generation(extension_id) + 1
    )
    for key in [key for key in _ephemeral_rooms if key[0] == extension_id]:
        room = _ephemeral_rooms.pop(key, None)
        if room:
            if room.scheduler_task and not room.scheduler_task.done():
                room.scheduler_task.cancel()
            room.changed.set()
        entry = _channel_queues.pop(key, None)
        if not entry:
            continue
        while not entry.queue.empty():
            job = entry.queue.get_nowait()
            if not job.future.done():
                job.future.set_exception(
                    PermissionError("Authoritative channel execution was invalidated.")
                )
            entry.queue.task_done()
        if not entry.worker.done():
            entry.worker.cancel()


async def get_authoritative_channel_state(
    extension_id: str,
    room_id: str,
    owner_id: str,
    *,
    max_bytes: int | None = None,
    persistence: str = "durable",
) -> AuthoritativeChannelState:
    if persistence == "ephemeral":
        if not broker.in_handler():
            result = await broker.call(
                extension_id,
                "state",
                {
                    "room_id": room_id,
                    "owner_id": owner_id,
                    "max_bytes": max_bytes,
                    "expected_generation": _remote_generations.get(
                        (extension_id, room_id, owner_id)
                    ),
                },
            )
            return AuthoritativeChannelState(**result["state"])
        _check_actor_ownership(extension_id)
        room = _get_ephemeral_room(
            extension_id,
            room_id,
            owner_id,
            max_active_rooms=1,
            create=False,
        )
        state = room.state
        if (
            max_bytes is not None
            and state.has_snapshot
            and len(json.dumps(state.snapshot, allow_nan=False).encode()) > max_bytes
        ):
            raise ValueError("Authoritative channel snapshot exceeds the host limit.")
        return state
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
    *,
    persistence: str = "durable",
) -> int:
    if persistence == "ephemeral":
        if not broker.in_handler():
            result = await broker.call(
                extension_id,
                "sequence",
                {"room_id": room_id, "principal_id": principal_id},
            )
            return int(result["sequence"])
        _check_actor_ownership(extension_id)
        room = _ephemeral_rooms.get((extension_id, room_id))
        return room.principal_sequences.get(principal_id, 0) if room else 0
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


def get_authoritative_channel_generation(
    extension_id: str, room_id: str, owner_id: str
) -> str:
    if not broker.is_owner(extension_id):
        generation = _remote_generations.get((extension_id, room_id, owner_id))
        if not generation:
            raise PermissionError("Authoritative channel room was not found.")
        return generation
    room = _ephemeral_rooms.get((extension_id, room_id))
    if not room or room.owner_id != owner_id:
        raise PermissionError("Authoritative channel room was not found.")
    return room.generation


async def wait_authoritative_channel_state_change(  # noqa: C901
    extension_id: str,
    room_id: str,
    owner_id: str,
    after_version: int,
    *,
    max_bytes: int | None = None,
) -> AuthoritativeChannelState | None:
    if not broker.is_owner(extension_id):
        while True:
            result = await broker.call(
                extension_id,
                "state",
                {
                    "room_id": room_id,
                    "owner_id": owner_id,
                    "max_bytes": max_bytes,
                    "expected_generation": _remote_generations.get(
                        (extension_id, room_id, owner_id)
                    ),
                },
            )
            if result["generation"] != _remote_generations.get(
                (extension_id, room_id, owner_id)
            ):
                return None
            state = AuthoritativeChannelState(**result["state"])
            if state.version > after_version:
                return state
            await asyncio.sleep(0.05)
    _check_actor_ownership(extension_id)
    room = _ephemeral_rooms.get((extension_id, room_id))
    if not room or room.owner_id != owner_id:
        return None
    while room.state.version <= after_version:
        room.changed.clear()
        if room.state.version > after_version:
            break
        try:
            await asyncio.wait_for(room.changed.wait(), timeout=0.5)
        except asyncio.TimeoutError:
            _check_actor_ownership(extension_id)
        if _ephemeral_rooms.get((extension_id, room_id)) is not room:
            return None
    state = room.state
    if (
        max_bytes is not None
        and state.has_snapshot
        and len(json.dumps(state.snapshot, allow_nan=False).encode()) > max_bytes
    ):
        raise ValueError("Authoritative channel snapshot exceeds the host limit.")
    return state


async def reserve_authoritative_connection(
    extension_id: str,
    room_id: str,
    owner_id: str,
    connection_id: str,
    *,
    max_active_rooms: int,
    max_connections_per_room: int,
    persistence: str = "durable",
) -> bool:
    if persistence == "ephemeral":
        if not broker.in_handler():
            result = await broker.call(
                extension_id,
                "reserve",
                {
                    "room_id": room_id,
                    "owner_id": owner_id,
                    "connection_id": connection_id,
                    "max_active_rooms": max_active_rooms,
                    "max_connections_per_room": max_connections_per_room,
                },
            )
            if result["reserved"]:
                key = (extension_id, room_id, owner_id)
                _remote_generations[key] = result["generation"]
                _remote_connection_rooms[(extension_id, connection_id)] = key
            return bool(result["reserved"])
        _check_actor_ownership(extension_id)
        await _restore_ephemeral_room(extension_id, room_id, owner_id, max_active_rooms)
        room = _get_ephemeral_room(
            extension_id,
            room_id,
            owner_id,
            max_active_rooms=max_active_rooms,
            create=True,
        )
        if len(room.connections) >= max_connections_per_room:
            return False
        room.connections[connection_id] = (
            int(time.time() * 1000) + _EPHEMERAL_CONNECTION_MS
        )
        room.last_activity_ms = int(time.time() * 1000)
        return True
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
    extension_id: str,
    room_id: str,
    connection_id: str,
    *,
    persistence: str = "durable",
) -> bool:
    if persistence == "ephemeral":
        if not broker.in_handler():
            result = await broker.call(
                extension_id,
                "renew",
                {"room_id": room_id, "connection_id": connection_id},
            )
            return bool(result["renewed"])
        _check_actor_ownership(extension_id)
        room = _ephemeral_rooms.get((extension_id, room_id))
        now_ms = int(time.time() * 1000)
        if not room or room.connections.get(connection_id, 0) <= now_ms:
            if room:
                room.connections.pop(connection_id, None)
            return False
        room.connections[connection_id] = now_ms + _EPHEMERAL_CONNECTION_MS
        room.last_activity_ms = now_ms
        return True
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
    extension_id: str,
    connection_id: str,
    *,
    room_id: str | None = None,
    persistence: str = "durable",
) -> None:
    if persistence == "ephemeral":
        if not broker.in_handler():
            try:
                await broker.call(
                    extension_id,
                    "release",
                    {"room_id": room_id, "connection_id": connection_id},
                )
            finally:
                key = _remote_connection_rooms.pop((extension_id, connection_id), None)
                if key and key not in _remote_connection_rooms.values():
                    _remote_generations.pop(key, None)
            return
        _check_actor_ownership(extension_id)
        room = _ephemeral_rooms.get((extension_id, room_id or ""))
        if room:
            room.connections.pop(connection_id, None)
            room.last_activity_ms = int(time.time() * 1000)
            if (
                not room.connections
                and not room.pending_jobs
                and not room.state.has_snapshot
            ):
                _ephemeral_rooms.pop((extension_id, room_id or ""), None)
        return
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


async def _run_channel_queue(  # noqa: C901
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
            await _release_channel_job(job)
            queue.task_done()
            continue
        try:
            result = await _execute_channel_job(job)
        except asyncio.CancelledError:
            if not job.future.done():
                job.future.set_exception(
                    PermissionError("Authoritative channel execution was invalidated.")
                )
            raise
        except Exception as exc:
            if not job.future.done():
                job.future.set_exception(exc)
        else:
            if not job.future.done():
                job.future.set_result(result)
        finally:
            await _release_channel_job(job)
            queue.task_done()


async def _execute_channel_job(job: _ChannelJob) -> dict[str, Any]:  # noqa: C901
    channel = job.extension.config.authoritative_channel
    if not channel:
        raise PermissionError("Authoritative channel dispatch is not enabled.")
    if getattr(channel, "persistence", "durable") == "ephemeral":
        return await _execute_ephemeral_channel_job(job)
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
        job.execution_sequence = sequence
        result = await _invoke_room_job(job, sequence, state, now_ms)
        if _authoritative_job_rejected(job.action, result):
            raise AuthoritativeChannelRejectedError(
                "Authoritative WASM channel rejected the action."
            )
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


async def _execute_ephemeral_channel_job(  # noqa: C901
    job: _ChannelJob,
) -> dict[str, Any]:
    channel = job.extension.config.authoritative_channel
    if not channel:
        raise PermissionError("Authoritative channel dispatch is not enabled.")
    room = _ephemeral_rooms.get((job.extension.id, job.room_id))
    if not room or room.generation != job.actor_generation:
        raise PermissionError("Ephemeral authoritative channel generation expired.")
    if job.policy_generation != get_ephemeral_authoritative_extension_generation(
        job.extension.id
    ):
        raise PermissionError("Ephemeral authoritative channel policy changed.")
    if room.owner_id != job.owner_id:
        raise PermissionError("Authoritative channel room owner does not match.")
    if job.action in {"event", "schedule"} and job.room_generation != room.generation:
        raise PermissionError("Ephemeral authoritative channel generation expired.")

    state = room.state
    now_ms = int(time.time() * 1000)
    event_timestamps = state.event_timestamps
    if job.action == "schedule":
        if channel.schedule_interval_ms is None:
            raise PermissionError("Channel scheduling is not configured.")
        if now_ms - state.last_schedule_ms < channel.schedule_interval_ms:
            return {"_hostSkipped": True}
        room.state = AuthoritativeChannelState(
            state.sequence,
            state.version,
            now_ms,
            state.snapshot,
            state.has_snapshot,
            event_timestamps,
        )
    elif job.action == "event":
        if not job.principal_id or job.client_sequence is None:
            raise ValueError("Authoritative event identity is incomplete.")
        if (
            job.principal_id not in room.principal_sequences
            and len(room.principal_sequences) >= _MAX_EPHEMERAL_PRINCIPALS_PER_ROOM
        ):
            raise AuthoritativeChannelBackpressureError(
                "Ephemeral authoritative room principal limit is full."
            )
        if job.client_sequence <= room.principal_sequences.get(job.principal_id, 0):
            raise ValueError("Authoritative event sequence is stale.")
        event_timestamps = [
            timestamp for timestamp in event_timestamps if now_ms - timestamp < 1000
        ]
        if len(event_timestamps) >= channel.max_events_per_second:
            raise ValueError("Authoritative channel event rate exceeded.")
        event_timestamps.append(now_ms)
        room.state = AuthoritativeChannelState(
            state.sequence,
            state.version,
            state.last_schedule_ms,
            state.snapshot,
            state.has_snapshot,
            event_timestamps,
        )

    if job.action in {"event", "schedule"}:
        await _validate_current_channel_permissions(job)
    sequence = state.sequence + (0 if job.action == "authorize" else 1)
    job.execution_sequence = sequence
    result = await _invoke_room_job(job, sequence, state, now_ms)
    _check_actor_ownership(job.extension.id)
    if _authoritative_job_rejected(job.action, result):
        raise AuthoritativeChannelRejectedError(
            "Authoritative WASM channel rejected the action."
        )
    if job.action == "api" and isinstance(result, dict) and result.get("ok") is False:
        return result

    data = result.get("data")
    has_snapshot, snapshot = _returned_snapshot(
        job.action,
        data,
        state.has_snapshot,
        max_bytes=job.limits["wasm_runtime_max_authoritative_state_bytes"],
    )
    if job.action in {"event", "schedule"} and not has_snapshot:
        raise ValueError("Authoritative channel handler must return a state snapshot.")
    if channel.result_table and has_snapshot and isinstance(snapshot, dict):
        result_data = snapshot.get(channel.result_field)
        if result_data is not None:
            if not isinstance(result_data, dict):
                raise ValueError("Authoritative result must be an object.")
            database = await _database(job.extension.id)
            async with database.connect() as conn:
                async with _transaction(conn):
                    await broker.assert_owner(job.extension.id, conn=conn)
                    await storage_insert_immutable_row(
                        conn,
                        job.extension.id,
                        channel.result_table,
                        {**result_data, "id": job.room_id},
                        job.owner_id,
                    )

    room.state = AuthoritativeChannelState(
        sequence=sequence if job.action != "authorize" else state.sequence,
        version=state.version + int(has_snapshot),
        last_schedule_ms=room.state.last_schedule_ms,
        snapshot=snapshot if has_snapshot else state.snapshot,
        has_snapshot=has_snapshot or state.has_snapshot,
        event_timestamps=room.state.event_timestamps,
    )
    if job.action == "event" and job.principal_id and job.client_sequence is not None:
        room.principal_sequences[job.principal_id] = job.client_sequence
    room.last_activity_ms = now_ms
    if has_snapshot or job.action == "authorize":
        broker.publish_state(
            job.extension.id,
            job.room_id,
            job.owner_id,
            asdict(room.state),
            room.generation,
            max_rooms=channel.max_active_rooms,
        )
        room.changed.set()
    if (
        job.action == "authorize"
        and channel.on_schedule
        and channel.schedule_interval_ms
    ):
        _start_ephemeral_room_schedule(job, room, channel)
    return result


def _start_ephemeral_room_schedule(  # noqa: C901
    job: _ChannelJob, room: _EphemeralRoom, channel: Any
) -> None:
    if room.scheduler_task and not room.scheduler_task.done():
        return
    if not room.connections:
        return
    extension = job.extension
    room_id, owner_id = job.room_id, job.owner_id
    limits = dict(job.limits)
    generation = room.generation
    permissions = list(job.permissions or [])
    policy_generation = job.policy_generation
    interval = channel.schedule_interval_ms / 1000
    rejection_limit = 3

    async def tick() -> None:  # noqa: C901
        consecutive_rejections = 0
        try:
            while settings.lnbits_running:
                remaining = (
                    room.state.last_schedule_ms
                    + channel.schedule_interval_ms
                    - int(time.time() * 1000)
                ) / 1000
                await asyncio.sleep(min(interval, max(0.001, remaining)))
                _check_actor_ownership(extension.id)
                if _ephemeral_rooms.get((extension.id, room_id)) is not room:
                    return
                if room.generation != generation or room.owner_id != owner_id:
                    return
                now_ms = int(time.time() * 1000)
                for connection_id, deadline in list(room.connections.items()):
                    if deadline <= now_ms:
                        room.connections.pop(connection_id, None)
                if not room.connections:
                    return
                try:
                    await run_authoritative_channel_export(
                        extension,
                        room_id,
                        owner_id,
                        channel.on_schedule,
                        {},
                        limits=limits,
                        action="schedule",
                        room_generation=generation,
                        permissions=permissions,
                        policy_generation=policy_generation,
                    )
                    consecutive_rejections = 0
                except AuthoritativeChannelBackpressureError:
                    await asyncio.sleep(interval)
                    continue
                except AuthoritativeChannelRejectedError:
                    consecutive_rejections += 1
                    logger.warning(
                        f"WASM authoritative schedule rejected for "
                        f"{extension.id}:{room_id} export {channel.on_schedule} "
                        f"(AuthoritativeChannelRejectedError; "
                        f"{consecutive_rejections}/{rejection_limit})."
                    )
                    if consecutive_rejections >= rejection_limit:
                        return
                    await asyncio.sleep(interval)
                    continue
                except PermissionError as exc:
                    logger.warning(
                        f"WASM authoritative schedule stopped for "
                        f"{extension.id}:{room_id} export {channel.on_schedule} "
                        f"({exc.__class__.__name__})."
                    )
                    return
                except Exception as exc:
                    logger.warning(
                        f"WASM authoritative schedule failed for "
                        f"{extension.id}:{room_id} export {channel.on_schedule} "
                        f"({exc.__class__.__name__})."
                    )
                    await asyncio.sleep(interval)
        except PermissionError:
            logger.warning(
                f"WASM authoritative schedule stopped for "
                f"{extension.id}:{room_id} export {channel.on_schedule} "
                "(PermissionError)."
            )
            return
        except asyncio.CancelledError:
            return

    room.scheduler_task = asyncio.create_task(tick())


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

    cached_authorization = job.persistence == "ephemeral" and job.action in {
        "event",
        "schedule",
    }
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
        preauthorized_permissions=(job.permissions if cached_authorization else None),
        runtime_limits=(job.limits if cached_authorization else None),
        ephemeral_authoritative_execution=job.persistence == "ephemeral",
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
    if job.persistence == "ephemeral":
        context["generation"] = job.actor_generation
    if job.action == "event":
        event = {
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
        if job.persistence == "ephemeral":
            event["generation"] = job.actor_generation
        return event
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
    except BaseException:
        stop_renewal.set()
        try:
            with suppress(Exception, asyncio.CancelledError):
                await renewal
        finally:
            await _release_room_lease(database, room_id, lease)
        raise
    else:
        stop_renewal.set()
        try:
            await renewal
        finally:
            await _release_room_lease(database, room_id, lease)


async def _renew_room_lease(
    database: Database,
    room_id: str,
    lease: str,
    lease_ms: int,
    stop: asyncio.Event,
) -> None:
    interval = lease_ms / 3000
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


def _check_actor_ownership(extension_id: str) -> None:
    if not broker.check_owner(extension_id):
        raise PermissionError("Authoritative room ownership expired.")
    epoch = broker.epoch(extension_id)
    if extension_id in _broker_epochs and _broker_epochs[extension_id] != epoch:
        invalidate_ephemeral_authoritative_extension(extension_id)
    _broker_epochs[extension_id] = epoch


async def _dispatch_ephemeral_operation(
    extension_id: str, operation: str, payload: dict[str, Any]
) -> dict[str, Any]:
    _check_actor_ownership(extension_id)
    if operation == "export":
        from lnbits.core.crud.users import get_account
        from lnbits.core.models.extensions import ExtensionPermission
        from lnbits.core.wasm_ext.wasm.invoke import _get_registered_extension

        extension = _broker_extensions.get(extension_id) or _get_registered_extension(
            extension_id
        )
        options = payload.get("invoke_options") or {}
        account_id = options.pop("broker_account_id", None)
        if account_id:
            options["user"] = await get_account(account_id)
            if options["user"] is None:
                raise PermissionError("Authoritative account was not found.")
        payload["invoke_options"] = options
        payload["permissions"] = [
            ExtensionPermission.parse_obj(item)
            for item in payload.get("permissions", [])
        ]
        # Generations are local policy counters; the broker lease epoch propagates
        # revocation across workers before any replacement actor can execute.
        payload["policy_generation"] = get_ephemeral_authoritative_extension_generation(
            extension_id
        )
        return await run_authoritative_channel_export(extension, **payload)
    if operation == "state":
        payload.pop("expected_generation", None)
        state = await get_authoritative_channel_state(
            extension_id, **payload, persistence="ephemeral"
        )
        return {
            "state": asdict(state),
            "generation": get_authoritative_channel_generation(
                extension_id, payload["room_id"], payload["owner_id"]
            ),
        }
    if operation == "sequence":
        return {
            "sequence": await get_authoritative_principal_sequence(
                extension_id, **payload, persistence="ephemeral"
            )
        }
    if operation == "reserve":
        reserved = await reserve_authoritative_connection(
            extension_id, **payload, persistence="ephemeral"
        )
        return {
            "reserved": reserved,
            "generation": (
                get_authoritative_channel_generation(
                    extension_id, payload["room_id"], payload["owner_id"]
                )
                if reserved
                else None
            ),
        }
    if operation == "renew":
        return {
            "renewed": await renew_authoritative_connection(
                extension_id, **payload, persistence="ephemeral"
            )
        }
    if operation == "release":
        await release_authoritative_connection(
            extension_id, **payload, persistence="ephemeral"
        )
        return {}
    raise ValueError("Unknown authoritative room operation.")


broker.configure(_dispatch_ephemeral_operation)


async def _validate_current_channel_permissions(job: _ChannelJob) -> None:
    from lnbits.core.crud.extensions import get_installed_extension

    installed = await get_installed_extension(job.extension.id)
    if (
        not installed
        or not installed.active
        or not installed.is_wasm
        or settings.lnbits_extensions_deactivate_all
    ):
        raise PermissionError("Authoritative extension is not active.")
    ids = {item.id for item in (installed.permissions or [])}
    if not {"websocket.subscribe", "websocket.authoritative"}.issubset(ids):
        raise PermissionError("Authoritative channel permission is not granted.")

    def grants(items: list[Any]) -> str:
        normalized = [item.dict() if hasattr(item, "dict") else item for item in items]
        return json.dumps(
            sorted(normalized, key=lambda item: item["id"]), sort_keys=True
        )

    if grants(installed.permissions or []) != grants(job.permissions or []):
        raise PermissionError("Authoritative channel permissions changed.")
