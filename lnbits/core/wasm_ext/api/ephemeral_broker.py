# ruff: noqa: S608
# SQL identifiers are fixed host names and validated by _table_ref.

"""Database-coordinated single-owner broker for fast authoritative extensions.

The module deliberately depends on LNbits' per-extension database cache. Local
owner calls stay in memory; only requests received by a non-owner use the mailbox.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.db import SQLITE, Database

Handler = Callable[[str, str, dict[str, Any]], Awaitable[dict[str, Any]]]

_OWNER_TABLE = "lnbits_authoritative_broker_owner"
_INBOX_TABLE = "lnbits_authoritative_broker_inbox"
_STATE_TABLE = "lnbits_authoritative_broker_state"
_MAX_MESSAGE_BYTES = 1024 * 1024
_MAX_PENDING = 512
_MESSAGE_TTL_MS = 60_000
_DEFAULT_STATE_ROOMS = 16
_MAX_STATE_ROOMS = 128
_STATE_TTL_MS = 60_000
_MAX_IDLE_POLL_SECONDS = 0.2
_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)
_handler_context: contextvars.ContextVar[tuple[str, int] | None] = (
    contextvars.ContextVar("wasm_authoritative_broker_context", default=None)
)


class BrokerBackpressureError(ValueError):
    """The owner mailbox has reached its configured bound."""


class BrokerUnavailableError(PermissionError):
    """No current room owner is available to process the request."""


@dataclass
class _LocalOwner:
    epoch: int
    valid_until: float
    renew_task: asyncio.Task[None] | None = None
    inbox_task: asyncio.Task[None] | None = None
    handler_tasks: set[asyncio.Task[None]] = field(default_factory=set)
    cleanup_task: asyncio.Task[None] | None = None
    wake: asyncio.Event = field(default_factory=asyncio.Event)


class EphemeralBroker:
    """Automatic per-extension owner plus a bounded cross-worker DB mailbox."""

    def __init__(
        self,
        handler: Handler | None = None,
        *,
        lease_seconds: float = 6.0,
        poll_interval: float = 0.02,
        max_message_bytes: int = _MAX_MESSAGE_BYTES,
        max_pending: int = _MAX_PENDING,
    ) -> None:
        if lease_seconds < 3 or poll_interval <= 0 or max_pending < 1:
            raise ValueError("Invalid broker limits.")
        self.handler = handler
        self.lease_seconds = lease_seconds
        self.poll_interval = poll_interval
        self.max_message_bytes = min(max_message_bytes, _MAX_MESSAGE_BYTES)
        self.max_pending = min(max_pending, _MAX_PENDING)
        self._pid = os.getpid()
        self._worker_id = uuid4().hex
        self._owners: dict[str, _LocalOwner] = {}
        self._extension_locks: dict[str, asyncio.Lock] = {}
        self._staged_states: dict[
            str, OrderedDict[tuple[str, str], tuple[int, str, str]]
        ] = {}
        self._state_room_limits: dict[str, int] = {}
        self._init_lock: asyncio.Lock | None = None

    @property
    def worker_id(self) -> str:
        # Avoid sharing a pre-fork identity if the broker was imported before
        # Uvicorn/Gunicorn created its workers.
        pid = os.getpid()
        if pid != self._pid:
            self._pid = pid
            self._worker_id = uuid4().hex
            self._owners.clear()
        return self._worker_id

    def configure(self, handler: Handler) -> None:
        self.handler = handler

    def is_owner(self, extension_id: str) -> bool:
        return self.check_owner(extension_id)

    def check_owner(self, extension_id: str) -> bool:
        if os.getpid() != self._pid:
            _ = self.worker_id
        owner = self._owners.get(extension_id)
        if not owner or owner.valid_until <= time.monotonic():
            return False
        return True

    def epoch(self, extension_id: str) -> int:
        owner = self._owners.get(extension_id)
        if not owner or not self.check_owner(extension_id):
            raise PermissionError("Authoritative extension ownership is not valid.")
        return owner.epoch

    def publish_state(
        self,
        extension_id: str,
        room_id: str,
        owner_id: str,
        state: dict[str, Any],
        generation: str,
        *,
        max_rooms: int = _DEFAULT_STATE_ROOMS,
    ) -> None:
        """Stage the newest active-room snapshot for the owner poller to flush."""
        self._validate_state_key(room_id, "room_id")
        self._validate_state_key(owner_id, "owner_id")
        if not isinstance(generation, str) or not generation or len(generation) > 128:
            raise ValueError("Invalid authoritative room generation.")
        if not isinstance(state, dict):
            raise ValueError("Authoritative room state must be an object.")
        if (
            isinstance(max_rooms, bool)
            or not isinstance(max_rooms, int)
            or max_rooms < 1
        ):
            raise ValueError("Invalid authoritative room limit.")
        capacity = min(max_rooms, _MAX_STATE_ROOMS)
        epoch = self.epoch(extension_id)
        state_json = json.dumps(state, allow_nan=False, separators=(",", ":"))
        result_json = json.dumps(
            {"state": state, "generation": generation},
            allow_nan=False,
            separators=(",", ":"),
        )
        if len(result_json.encode()) > self.max_message_bytes:
            raise ValueError("Authoritative broker response is too large.")
        key = (room_id, owner_id)
        staged = self._staged_states.setdefault(extension_id, OrderedDict())
        self._state_room_limits[extension_id] = capacity
        staged[key] = (epoch, generation, state_json)
        staged.move_to_end(key)
        while len(staged) > capacity:
            staged.popitem(last=False)
        self._owners[extension_id].wake.set()

    async def call(
        self,
        extension_id: str,
        operation: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float = 2.0,
    ) -> dict[str, Any]:
        if not self.handler:
            raise RuntimeError("Authoritative broker handler is not configured.")
        self._validate_call(extension_id, operation, payload, timeout_seconds)
        if operation == "state" and not self.check_owner(extension_id):
            return await self._remote_state_call(extension_id, payload, timeout_seconds)
        epoch: int | None
        if self.check_owner(extension_id):
            epoch = self.epoch(extension_id)
            result = await self._dispatch(extension_id, operation, payload, epoch)
            if not self.check_owner(extension_id) or self.epoch(extension_id) != epoch:
                raise PermissionError("Authoritative extension ownership expired.")
            return result

        async with self._extension_locks.setdefault(extension_id, asyncio.Lock()):
            if self.check_owner(extension_id):
                epoch = self.epoch(extension_id)
            else:
                owner = await self._read_owner(extension_id)
                epoch = (
                    None
                    if owner and owner["expires_at_ms"] > owner["now_ms"]
                    else await self._try_claim(extension_id)
                )
        if epoch is not None:
            self._start_owner_tasks(extension_id)
            result = await self._dispatch(extension_id, operation, payload, epoch)
            if not self.check_owner(extension_id) or self.epoch(extension_id) != epoch:
                raise PermissionError("Authoritative extension ownership expired.")
            return result

        if operation == "state":
            return await self._remote_state_call(extension_id, payload, timeout_seconds)

        return await self._remote_call(
            extension_id, operation, payload, timeout_seconds
        )

    async def _remote_state_call(
        self,
        extension_id: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        room_id = payload.get("room_id")
        owner_id = payload.get("owner_id")
        self._validate_state_key(room_id, "room_id")
        self._validate_state_key(owner_id, "owner_id")
        max_bytes = payload.get("max_bytes")
        if max_bytes is not None and (
            isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or max_bytes < 1
        ):
            raise ValueError("Invalid authoritative state size limit.")
        expected_generation = (
            payload.get("expected_generation")
            or payload.get("generation")
            or payload.get("room_generation")
        )
        if expected_generation is not None and (
            not isinstance(expected_generation, str) or len(expected_generation) > 128
        ):
            raise ValueError("Invalid authoritative room generation.")
        deadline = time.monotonic() + timeout_seconds
        interval = 0.05
        while time.monotonic() < deadline:
            try:
                cache = await self._read_published_state(extension_id, payload)
            except (PermissionError, ValueError):
                raise
            except Exception:
                raise BrokerUnavailableError(
                    "Authoritative snapshot could not be verified."
                ) from None
            if cache is not None:
                return cache
            await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))
            interval = min(interval * 2, _MAX_IDLE_POLL_SECONDS)
        raise BrokerUnavailableError("Authoritative snapshot is not available.")

    async def _read_published_state(
        self, extension_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        database = await self._database(extension_id)
        owner_table = self._table_ref(database, _OWNER_TABLE)
        state_table = self._table_ref(database, _STATE_TABLE)
        room_id = payload["room_id"]
        owner_id = payload["owner_id"]
        now_sql = self._db_now_sql(database)
        async with database.connect() as conn:
            row = await conn.fetchone(
                f"""SELECT owner.worker_id, owner.epoch AS owner_epoch,
                        owner.expires_at_ms AS owner_expires_at_ms,
                        {now_sql} AS now_ms, state.lease_epoch AS state_epoch,
                        state.room_generation, state.state_json,
                        state.expires_at_ms AS state_expires_at_ms
                    FROM {owner_table} AS owner
                    LEFT JOIN {state_table} AS state
                        ON state.room_id = :room_id AND state.owner_id = :owner_id
                            AND state.lease_epoch = owner.epoch
                            AND state.expires_at_ms > {now_sql}
                    WHERE owner.id = 1""",
                {"room_id": room_id, "owner_id": owner_id},
            )
        if (
            not row
            or not row["worker_id"]
            or int(row["owner_expires_at_ms"]) <= int(row["now_ms"])
            or row["state_json"] is None
        ):
            return None
        expected_generation = (
            payload.get("expected_generation")
            or payload.get("generation")
            or payload.get("room_generation")
        )
        if expected_generation and expected_generation != row["room_generation"]:
            return None
        if int(row["state_epoch"]) != int(row["owner_epoch"]):
            return None
        state = json.loads(row["state_json"])
        if not isinstance(state, dict):
            return None
        max_bytes = payload.get("max_bytes")
        snapshot = state.get("snapshot")
        if (
            max_bytes is not None
            and state.get("has_snapshot")
            and len(json.dumps(snapshot, allow_nan=False).encode()) > max_bytes
        ):
            raise ValueError("Authoritative channel snapshot exceeds the host limit.")
        result = {"state": state, "generation": row["room_generation"]}
        if (
            len(json.dumps(result, allow_nan=False, separators=(",", ":")).encode())
            > self.max_message_bytes
        ):
            raise ValueError("Authoritative broker response is too large.")
        return result

    async def recover_state(
        self, extension_id: str, room_id: str, owner_id: str
    ) -> dict[str, Any] | None:
        """Read the last bounded checkpoint only inside the new owner's fence.

        Expired publications remain recovery checkpoints, never client-visible
        state. Room-count pruning still bounds retention; this is not a ledger.
        """
        database = await self._database(extension_id)
        table = self._table_ref(database, _STATE_TABLE)
        async with database.connect() as conn:
            async with self._transaction(conn):
                epoch = await self.assert_owner(extension_id, conn)
                row = await conn.fetchone(
                    f"""SELECT state_json FROM {table}
                        WHERE room_id = :room AND owner_id = :owner
                            AND lease_epoch <= :epoch""",
                    {"room": room_id, "owner": owner_id, "epoch": epoch},
                )
        if not row:
            return None
        encoded = row["state_json"]
        if len(encoded.encode()) > self.max_message_bytes:
            raise BrokerUnavailableError(
                "Authoritative checkpoint exceeds host limits."
            )
        state = json.loads(encoded)
        if not isinstance(state, dict):
            raise BrokerUnavailableError("Authoritative checkpoint is invalid.")
        return state

    async def _flush_staged_states(self, extension_id: str, epoch: int) -> None:
        staged = self._staged_states.get(extension_id)
        if not staged:
            return
        capacity = min(
            self._state_room_limits.get(extension_id, _DEFAULT_STATE_ROOMS),
            _MAX_STATE_ROOMS,
        )
        batch = [
            (key, value)
            for key, value in list(staged.items())[: min(capacity, _MAX_STATE_ROOMS)]
            if value[0] == epoch
        ]
        if not batch:
            return
        database = await self._database(extension_id)
        table = self._table_ref(database, _STATE_TABLE)
        async with database.connect() as conn:
            async with self._transaction(conn):
                await self._assert_owner_on_connection(
                    extension_id, epoch, conn, database
                )
                now = await self._db_now_ms(conn, database)
                for (room_id, owner_id), (state_epoch, generation, state_json) in batch:
                    await conn.conn.execute(
                        text(f"""INSERT INTO {table}
                            (room_id, owner_id, lease_epoch, room_generation,
                             state_json, updated_at_ms, expires_at_ms)
                            VALUES (:room_id, :owner_id, :epoch, :generation,
                                    :state, :now, :expires)
                            ON CONFLICT (room_id, owner_id) DO UPDATE SET
                                lease_epoch = excluded.lease_epoch,
                                room_generation = excluded.room_generation,
                                state_json = excluded.state_json,
                                updated_at_ms = excluded.updated_at_ms,
                                expires_at_ms = excluded.expires_at_ms"""),
                        {
                            "room_id": room_id,
                            "owner_id": owner_id,
                            "epoch": state_epoch,
                            "generation": generation,
                            "state": state_json,
                            "now": now,
                            "expires": now + _STATE_TTL_MS,
                        },
                    )
                await conn.conn.execute(
                    text(f"""DELETE FROM {table}
                        WHERE (room_id, owner_id) IN (
                            SELECT room_id, owner_id FROM (
                                SELECT room_id, owner_id,
                                    ROW_NUMBER() OVER (
                                        ORDER BY updated_at_ms DESC, room_id, owner_id
                                    ) AS position
                                FROM {table}
                            ) AS ranked WHERE position > :capacity
                        )"""),
                    {"capacity": capacity},
                )
        current = self._staged_states.get(extension_id)
        if (
            current
            and self.check_owner(extension_id)
            and self.epoch(extension_id) == epoch
        ):
            for key, value in batch:
                if current.get(key) == value:
                    current.pop(key, None)
            if not current:
                self._staged_states.pop(extension_id, None)

    async def assert_owner(self, extension_id: str, conn: Any = None) -> int:
        """Fence a durable side effect in its existing database transaction."""
        context = _handler_context.get()
        owner = self._owners.get(extension_id)
        if (
            not context
            or context[0] != extension_id
            or not owner
            or context[1] != owner.epoch
            or not self.check_owner(extension_id)
        ):
            raise PermissionError("Authoritative extension ownership expired.")
        database = await self._database(extension_id)
        own_connection = conn is None
        if own_connection:
            async with database.connect() as opened:
                return await self._assert_owner_on_connection(
                    extension_id, context[1], opened, database
                )
        return await self._assert_owner_on_connection(
            extension_id, context[1], conn, database
        )

    async def invalidate(self, extension_id: str) -> None:
        """Fence the current owner and discard its local actor tasks."""
        database = await self._database(extension_id)
        state = self._owners.get(extension_id)
        local_owner = bool(state and self.check_owner(extension_id))
        # Stop a local actor before releasing its lease. A remote revocation
        # fences it immediately but must preserve its expiry to prevent overlap.
        if state:
            await self._drop_owner(extension_id, fence=False)
        async with database.connect() as conn:
            table = self._table_ref(database, _OWNER_TABLE)
            async with self._transaction(conn):
                await conn.conn.execute(text(f"""INSERT INTO {table}
                            (id,
                            worker_id, epoch, expires_at_ms)
                            VALUES (1, NULL, 0, 0) ON CONFLICT (id) DO NOTHING"""))
                await conn.conn.execute(
                    text(f"UPDATE {table} SET epoch = epoch WHERE id = 1")
                )
                now = await self._db_now_ms(conn, database)
                params: dict[str, Any] = {"id": 1, "now": now}
                where = "id = :id"
                if local_owner and state:
                    where += " AND worker_id = :worker AND epoch = :epoch"
                    params.update(worker=self.worker_id, epoch=state.epoch)
                release_lease = local_owner and state is not None
                expiry = (
                    "expires_at_ms = :now"
                    if release_lease
                    else "expires_at_ms = expires_at_ms"
                )
                if state and not release_lease:
                    # This broker knows the previous actor but its cached
                    # deadline elapsed; fence it without shortening DB lease.
                    where += " AND worker_id = :worker AND epoch = :epoch"
                    params.update(worker=self.worker_id, epoch=state.epoch)
                await conn.conn.execute(
                    text(f"""UPDATE {table}
                    SET worker_id = NULL, epoch = epoch + 1, {expiry}
                    WHERE {where}"""),
                    params,
                )

    async def close(self) -> None:
        for extension_id in list(self._owners):
            await self.invalidate(extension_id)

    async def _try_claim(self, extension_id: str) -> int | None:
        previous = self._owners.get(extension_id)
        if previous and not self.check_owner(extension_id):
            await self._drop_owner(extension_id)
        database = await self._database(extension_id)
        table = self._table_ref(database, _OWNER_TABLE)
        worker = self.worker_id
        sampled_at = time.monotonic()
        now_sql = self._db_now_sql(database)
        async with database.connect() as conn:
            async with self._transaction(conn):
                await conn.conn.execute(
                    text(f"""INSERT INTO {table} (id, worker_id, epoch, expires_at_ms)
                        VALUES (1, NULL, 0, 0) ON CONFLICT (id) DO NOTHING""")
                )
                result = await conn.conn.execute(
                    text(f"""UPDATE {table}
                        SET epoch = epoch + 1,
                            worker_id = :worker,
                            expires_at_ms = {now_sql} + :lease_ms
                        WHERE id = 1 AND expires_at_ms <= {now_sql}
                        RETURNING epoch, expires_at_ms"""),
                    {"worker": worker, "lease_ms": int(self.lease_seconds * 1000)},
                )
                row = result.fetchone()
                result.close()
                if not row:
                    return None
        epoch = int(row["epoch"])
        self._owners[extension_id] = _LocalOwner(
            epoch=epoch,
            valid_until=self._local_deadline(sampled_at),
        )
        return epoch

    async def _remote_call(  # noqa: C901
        self,
        extension_id: str,
        operation: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        database = await self._database(extension_id)
        inbox = self._table_ref(database, _INBOX_TABLE)
        body = json.dumps(payload, allow_nan=False, separators=(",", ":"))
        if len(body.encode()) > self.max_message_bytes:
            raise ValueError("Authoritative broker message is too large.")
        request_id = uuid4().hex
        owner_table = self._table_ref(database, _OWNER_TABLE)
        now_sql = self._db_now_sql(database)
        interval = self.poll_interval
        while time.monotonic() < deadline:
            owner = await self._read_owner(extension_id)
            if (
                owner
                and not owner["worker_id"]
                and owner["expires_at_ms"] > owner["now_ms"]
            ):
                await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))
                interval = min(
                    interval * 2, max(self.poll_interval, _MAX_IDLE_POLL_SECONDS)
                )
                continue
            if not owner or owner["expires_at_ms"] <= owner["now_ms"]:
                async with self._extension_locks.setdefault(
                    extension_id, asyncio.Lock()
                ):
                    if not self.check_owner(extension_id):
                        epoch = await self._try_claim(extension_id)
                        if epoch is not None:
                            self._start_owner_tasks(extension_id)
                            return await self._dispatch(
                                extension_id, operation, payload, epoch
                            )
                await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))
                interval = min(
                    interval * 2, max(self.poll_interval, _MAX_IDLE_POLL_SECONDS)
                )
                continue
            epoch = int(owner["epoch"])
            async with database.connect() as conn:
                async with self._transaction(conn):
                    await conn.conn.execute(text(f"""UPDATE {owner_table}
                                        SET epoch = epoch WHERE id = 1"""))
                    live_owner = await conn.fetchone(
                        f"""SELECT owner.worker_id, owner.epoch, owner.expires_at_ms,
                                {now_sql} AS now_ms,
                                (SELECT COUNT(*) FROM {inbox}
                                 WHERE expires_at_ms > {now_sql}
                                    AND status IN ('queued','processing'))
                                    AS pending_count
                            FROM {owner_table} AS owner WHERE owner.id = 1"""
                    )
                    if (
                        not live_owner
                        or int(live_owner["epoch"]) != epoch
                        or live_owner["worker_id"] != owner["worker_id"]
                        or int(live_owner["expires_at_ms"]) <= int(live_owner["now_ms"])
                    ):
                        continue
                    if int(live_owner["pending_count"]) >= self.max_pending:
                        raise BrokerBackpressureError(
                            "Authoritative broker mailbox is full."
                        )
                    await conn.conn.execute(
                        text(f"""INSERT INTO {inbox}
                            (request_id,
                                worker_id, owner_epoch, operation, payload_json,
                             status, response_json, error_type, error_message,
                             created_at_ms, expires_at_ms)
                            VALUES (:id, :worker, :epoch, :operation, :payload,
                                    'queued', NULL, NULL, NULL, :now, :expires)"""),
                        {
                            "id": request_id,
                            "worker": self.worker_id,
                            "epoch": epoch,
                            "operation": operation,
                            "payload": body,
                            "now": int(live_owner["now_ms"]),
                            "expires": int(live_owner["now_ms"])
                            + min(
                                _MESSAGE_TTL_MS, max(1000, int(timeout_seconds * 1000))
                            ),
                        },
                    )
            break
        else:
            raise TimeoutError("No authoritative extension owner became available.")

        interval = self.poll_interval
        previous_status = "queued"
        while time.monotonic() < deadline:
            async with database.connect() as conn:
                row = await conn.fetchone(
                    f"""SELECT request.status, request.owner_epoch,
                        request.response_json,
                            request.error_type, request.error_message,
                                request.expires_at_ms,
                            owner.worker_id AS owner_worker_id,
                                owner.epoch AS current_epoch,
                            owner.expires_at_ms AS owner_expires_at_ms,
                            {now_sql} AS now_ms
                        FROM {inbox} AS request
                        JOIN {owner_table} AS owner ON owner.id = 1
                        WHERE request.request_id = :id""",
                    {"id": request_id},
                )
            if not row:
                raise PermissionError("Authoritative broker request expired.")
            if (
                int(row["owner_epoch"]) != epoch
                or int(row["current_epoch"]) != epoch
                or row["owner_worker_id"] is None
                or int(row["owner_expires_at_ms"]) <= int(row["now_ms"])
            ):
                raise PermissionError(
                    "Authoritative room owner changed during request."
                )
            if row["status"] == "done":
                async with database.connect() as conn:
                    await conn.execute(
                        f"DELETE FROM {inbox} WHERE request_id = :id",
                        {"id": request_id},
                    )
                if row["error_type"]:
                    self._raise_remote_error(
                        row["error_type"], row["error_message"] or ""
                    )
                value = json.loads(row["response_json"] or "{}")
                if not isinstance(value, dict):
                    raise ValueError("Authoritative broker response is invalid.")
                return value
            if row["expires_at_ms"] <= row["now_ms"]:
                raise TimeoutError("Authoritative broker request expired.")
            if row["status"] != previous_status:
                interval = self.poll_interval
                previous_status = row["status"]
            await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))
            interval = min(
                interval * 2, max(self.poll_interval, _MAX_IDLE_POLL_SECONDS)
            )

        async with database.connect() as conn:
            await conn.execute(
                f"""UPDATE {inbox} SET status = 'abandoned'
                    WHERE request_id = :id AND status = 'queued'""",
                {"id": request_id},
            )
        raise TimeoutError("Authoritative broker request timed out.")

    async def _owner_loop(self, extension_id: str, epoch: int) -> None:
        try:
            await self._owner_poll_loop(extension_id, epoch)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Any uncertain shared-state read means this process must stop
            # dispatching and discard its cached actor immediately.
            await self._drop_owner(extension_id)

    async def _owner_poll_loop(  # noqa: C901
        self, extension_id: str, epoch: int
    ) -> None:
        database = await self._database(extension_id)
        inbox = self._table_ref(database, _INBOX_TABLE)
        next_state_flush = time.monotonic() + 0.05
        interval = self.poll_interval
        while self.check_owner(extension_id) and self.epoch(extension_id) == epoch:
            owner = self._owners[extension_id]
            owner.wake.clear()
            try:
                row = await self._read_owner(extension_id)
            except Exception:
                await self._drop_owner(extension_id)
                return
            if (
                not row
                or row["worker_id"] != self.worker_id
                or int(row["epoch"]) != epoch
                or int(row["expires_at_ms"]) <= int(row["now_ms"])
            ):
                await self._drop_owner(extension_id)
                return
            if time.monotonic() >= next_state_flush:
                await self._flush_staged_states(extension_id, epoch)
                next_state_flush = time.monotonic() + 0.05
            if len(self._owners[extension_id].handler_tasks) >= min(
                64, self.max_pending
            ):
                await asyncio.sleep(self.poll_interval)
                continue
            async with database.connect() as conn:
                now = await self._db_now_ms(conn, database)
                rows = await conn.fetchall(
                    f"""SELECT request_id, worker_id, operation, payload_json
                        FROM {inbox}
                        WHERE status = 'queued' AND owner_epoch = :epoch
                            AND expires_at_ms > :now
                        ORDER BY created_at_ms, request_id LIMIT :limit""",
                    {
                        "epoch": epoch,
                        "now": now,
                        "limit": min(64, self.max_pending) - len(owner.handler_tasks),
                    },
                )
                claimed = []
                for row in rows:
                    result = await conn.execute(
                        f"""UPDATE {inbox} SET status = 'processing'
                            WHERE request_id = :id AND status = 'queued'
                                AND owner_epoch = :epoch AND expires_at_ms > :now""",
                        {"id": row["request_id"], "epoch": epoch, "now": now},
                    )
                    if result.rowcount:
                        claimed.append(row)
            if not claimed:
                delay = interval
                if self._staged_states.get(extension_id):
                    delay = min(delay, max(0, next_state_flush - time.monotonic()))
                try:
                    await asyncio.wait_for(owner.wake.wait(), timeout=delay)
                    interval = self.poll_interval
                except TimeoutError:
                    interval = min(
                        interval * 2, max(self.poll_interval, _MAX_IDLE_POLL_SECONDS)
                    )
                continue
            interval = self.poll_interval
            for row in claimed:
                task = asyncio.create_task(
                    self._process_message(extension_id, epoch, row)
                )
                owner.handler_tasks.add(task)
                task.add_done_callback(owner.handler_tasks.discard)

    async def _process_message(
        self, extension_id: str, epoch: int, row: dict[str, Any]
    ) -> None:
        error_type = error_message = None
        response_json = None
        try:
            if not self.check_owner(extension_id) or self.epoch(extension_id) != epoch:
                raise PermissionError("Authoritative extension ownership expired.")
            payload = json.loads(row["payload_json"])
            response = await self._dispatch(
                extension_id, row["operation"], payload, epoch
            )
            response_json = json.dumps(response, allow_nan=False, separators=(",", ":"))
            if len(response_json.encode()) > self.max_message_bytes:
                raise ValueError("Authoritative broker response is too large.")
        except Exception as exc:
            error_type, error_message = self._safe_error(exc)

        database = await self._database(extension_id)
        inbox = self._table_ref(database, _INBOX_TABLE)
        try:
            async with database.connect() as conn:
                async with self._transaction(conn):
                    await self._assert_owner_on_connection(
                        extension_id, epoch, conn, database
                    )
                    await conn.conn.execute(
                        text(f"""UPDATE {inbox}
                            SET status = 'done', response_json = :response,
                                error_type = :error_type, error_message = :error_message
                            WHERE request_id = :id AND owner_epoch = :epoch
                                AND status = 'processing'"""),
                        {
                            "response": response_json,
                            "error_type": error_type,
                            "error_message": error_message,
                            "id": row["request_id"],
                            "epoch": epoch,
                        },
                    )
        except (PermissionError, TimeoutError):
            return
        except Exception:
            # An uncertain response commit must stop the owner, not leak a
            # background task traceback or acknowledge unverified completion.
            await self._drop_owner(extension_id)

    async def _dispatch(
        self,
        extension_id: str,
        operation: str,
        payload: dict[str, Any],
        epoch: int,
    ) -> dict[str, Any]:
        if not self.handler:
            raise RuntimeError("Authoritative broker handler is not configured.")
        if not self.check_owner(extension_id) or self.epoch(extension_id) != epoch:
            raise PermissionError("Authoritative extension ownership expired.")
        token = _handler_context.set((extension_id, epoch))
        try:
            result = await self.handler(extension_id, operation, payload)
            if not isinstance(result, dict):
                raise ValueError("Authoritative broker handlers must return an object.")
            json.dumps(result, allow_nan=False)
            if operation == "state":
                self._stage_state_result(extension_id, payload, result)
            if not self.check_owner(extension_id) or self.epoch(extension_id) != epoch:
                raise PermissionError("Authoritative extension ownership expired.")
            return result
        finally:
            _handler_context.reset(token)

    def _start_owner_tasks(self, extension_id: str) -> None:
        state = self._owners[extension_id]
        if not state.renew_task or state.renew_task.done():
            state.renew_task = asyncio.create_task(
                self._renew_loop(extension_id, state.epoch)
            )
        if not state.inbox_task or state.inbox_task.done():
            state.inbox_task = asyncio.create_task(
                self._owner_loop(extension_id, state.epoch)
            )
        if not state.cleanup_task or state.cleanup_task.done():
            state.cleanup_task = asyncio.create_task(
                self._cleanup_loop(extension_id, state.epoch)
            )

    async def _cleanup_loop(self, extension_id: str, epoch: int) -> None:
        try:
            database = await self._database(extension_id)
            inbox = self._table_ref(database, _INBOX_TABLE)
            while self.check_owner(extension_id) and self.epoch(extension_id) == epoch:
                await asyncio.sleep(5)
                async with database.connect() as conn:
                    now = await self._db_now_ms(conn, database)
                    await conn.execute(
                        f"""DELETE FROM {inbox}
                            WHERE expires_at_ms <= :now OR status = 'abandoned'""",
                        {"now": now},
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._drop_owner(extension_id)

    async def _renew_loop(self, extension_id: str, epoch: int) -> None:
        interval = self.lease_seconds / 3
        try:
            while self.check_owner(extension_id) and self.epoch(extension_id) == epoch:
                await asyncio.sleep(interval)
                database = await self._database(extension_id)
                table = self._table_ref(database, _OWNER_TABLE)
                async with database.connect() as conn:
                    sampled_at = time.monotonic()
                    now = await self._db_now_ms(conn, database)
                    result = await conn.execute(
                        f"""UPDATE {table} SET expires_at_ms = :expires
                            WHERE id = 1 AND worker_id = :worker AND epoch = :epoch
                                AND expires_at_ms > :now""",
                        {
                            "expires": now + int(self.lease_seconds * 1000),
                            "worker": self.worker_id,
                            "epoch": epoch,
                            "now": now,
                        },
                    )
                if not result.rowcount:
                    await self._drop_owner(extension_id)
                    return
                owner = self._owners.get(extension_id)
                if owner and owner.epoch == epoch:
                    owner.valid_until = self._local_deadline(sampled_at)
                    if not self.check_owner(extension_id):
                        await self._drop_owner(extension_id)
                        return
        except asyncio.CancelledError:
            return
        except Exception:
            # Never keep serving after an uncertain lease renewal.
            await self._drop_owner(extension_id)

    async def _assert_owner_on_connection(
        self, extension_id: str, epoch: int, conn: Any, database: Database
    ) -> int:
        table = self._table_ref(database, _OWNER_TABLE)
        if conn.type == SQLITE:
            # The caller must run this before other reads in its SQLite write
            # transaction; this first no-op update acquires its writer lock.
            await conn.conn.execute(
                text(f"UPDATE {table} SET epoch = epoch WHERE id = 1")
            )
            suffix = ""
        else:
            suffix = " FOR UPDATE"
        now = await self._db_now_ms(conn, database)
        row = await conn.fetchone(
            f"SELECT worker_id, epoch, expires_at_ms FROM {table} WHERE id = 1{suffix}"
        )
        if (
            not row
            or row["worker_id"] != self.worker_id
            or int(row["epoch"]) != epoch
            or int(row["expires_at_ms"]) <= now
        ):
            raise PermissionError("Authoritative extension ownership expired.")
        return epoch

    async def _read_owner(self, extension_id: str) -> dict[str, Any] | None:
        database = await self._database(extension_id)
        async with database.connect() as conn:
            row = await conn.fetchone(f"""SELECT worker_id, epoch, expires_at_ms,
                    {self._db_now_sql(database)} AS now_ms
                    FROM {self._table_ref(database, _OWNER_TABLE)} WHERE id = 1""")
        return row

    async def _database(self, extension_id: str) -> Database:
        self._validate_identifier(extension_id)
        await storage_crud._initialize_database_once(
            extension_id, "authoritative_broker", self._create_tables
        )
        return storage_crud._database(extension_id)

    async def _create_tables(self, database: Database) -> None:
        owner = self._table_ref(database, _OWNER_TABLE)
        inbox = self._table_ref(database, _INBOX_TABLE)
        async with database.connect() as conn:
            await conn.execute(f"""CREATE TABLE IF NOT EXISTS {owner} (
                id INTEGER PRIMARY KEY,
                worker_id TEXT,
                epoch {database.big_int} NOT NULL DEFAULT 0,
                expires_at_ms {database.big_int} NOT NULL DEFAULT 0
            )""")
            await conn.execute(f"""CREATE TABLE IF NOT EXISTS {inbox} (
                request_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                owner_epoch {database.big_int} NOT NULL,
                operation TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                response_json TEXT,
                error_type TEXT,
                error_message TEXT,
                created_at_ms {database.big_int} NOT NULL,
                expires_at_ms {database.big_int} NOT NULL
            )""")
            if database.type == SQLITE and database.schema:
                index = f"{database.schema}.{self._index_name(database)}"
                table = _INBOX_TABLE
            else:
                index = self._index_name(database)
                table = inbox
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {index} "
                f"ON {table} (status, owner_epoch, created_at_ms)"
            )
            await conn.execute(f"""CREATE TABLE IF NOT EXISTS
                {self._table_ref(database, _STATE_TABLE)} (
                room_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                lease_epoch {database.big_int} NOT NULL,
                room_generation TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at_ms {database.big_int} NOT NULL,
                expires_at_ms {database.big_int} NOT NULL,
                PRIMARY KEY (room_id, owner_id)
            )""")

    async def _db_now_ms(self, conn: Any, database: Database) -> int:
        row = await conn.fetchone(f"SELECT {self._db_now_sql(database)} AS now_ms")
        return int(row["now_ms"])

    def _db_now_sql(self, database: Database) -> str:
        return (
            "CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)"
            if database.type == SQLITE
            else "CAST(EXTRACT(EPOCH FROM clock_timestamp()) * 1000 AS BIGINT)"
        )

    @asynccontextmanager
    async def _transaction(self, conn: Any):
        if conn.type == SQLITE:
            await conn.conn.exec_driver_sql("BEGIN")
            try:
                yield
            except BaseException:
                await conn.conn.rollback()
                raise
            else:
                await conn.conn.commit()
            return
        async with conn.conn.begin():
            yield

    def _table_ref(self, database: Database, name: str) -> str:
        if not all(char in _IDENTIFIER_CHARS for char in name):
            raise ValueError("Invalid broker table name.")
        if database.schema:
            self._validate_identifier(database.schema)
            return f"{database.schema}.{name}"
        return name

    def _index_name(self, database: Database) -> str:
        # Keep index identifiers below PostgreSQL's 63-byte limit.
        schema = database.schema or "lnbits"
        return f"{schema[:12]}_broker_inbox_idx"

    def _stage_state_result(
        self,
        extension_id: str,
        payload: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        state = result.get("state")
        generation = result.get("generation")
        if isinstance(state, dict) and isinstance(generation, str) and generation:
            # Keep the capacity established by the channel's published state
            # instead of resetting it to the default on every cached read.
            capacity = self._state_room_limits.get(extension_id, _DEFAULT_STATE_ROOMS)
            self.publish_state(
                extension_id,
                payload["room_id"],
                payload["owner_id"],
                state,
                generation,
                max_rooms=capacity,
            )

    async def _drop_owner(self, extension_id: str, *, fence: bool = True) -> None:
        owner = self._owners.pop(extension_id, None)
        self._staged_states.pop(extension_id, None)
        self._state_room_limits.pop(extension_id, None)
        if not owner:
            return
        current = asyncio.current_task()
        tasks = [
            owner.renew_task,
            owner.inbox_task,
            owner.cleanup_task,
            *owner.handler_tasks,
        ]
        for task in tasks:
            if task and task is not current and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in tasks if task and task is not current),
            return_exceptions=True,
        )
        if fence:
            # Stop remote reads of snapshots for the dropped actor immediately.
            # Keep the old lease deadline so a replacement cannot overlap it.
            try:
                database = await self._database(extension_id)
                owner_table = self._table_ref(database, _OWNER_TABLE)
                async with database.connect() as conn:
                    async with self._transaction(conn):
                        if conn.type == SQLITE:
                            await conn.conn.execute(text(f"""UPDATE {owner_table}
                                        SET epoch = epoch WHERE id = 1"""))
                        now = await self._db_now_ms(conn, database)
                        await conn.conn.execute(
                            text(f"""UPDATE {owner_table}
                                SET worker_id = NULL, epoch = epoch + 1
                                WHERE id = 1 AND worker_id = :worker
                                    AND epoch = :epoch AND expires_at_ms > :now"""),
                            {
                                "worker": self.worker_id,
                                "epoch": owner.epoch,
                                "now": now,
                            },
                        )
            except Exception:
                # Local dispatch remains stopped; the cached DB lease still expires.
                return

    def _local_deadline(self, sampled_at: float) -> float:
        # Conservative relative to the DB-time sample: transaction/driver delay
        # consumes lease time instead of extending the local fast-path window.
        return sampled_at + self.lease_seconds - min(0.5, self.lease_seconds * 0.1)

    def _validate_call(
        self,
        extension_id: str,
        operation: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> None:
        self._validate_identifier(extension_id)
        if not isinstance(operation, str) or not operation or len(operation) > 64:
            raise ValueError("Invalid broker operation.")
        if not isinstance(payload, dict) or timeout_seconds <= 0:
            raise ValueError("Invalid broker request.")
        encoded = json.dumps(payload, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode()) > self.max_message_bytes:
            raise ValueError("Authoritative broker message is too large.")

    @staticmethod
    def _validate_identifier(value: str) -> None:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 128
            or not all(char in _IDENTIFIER_CHARS for char in value)
        ):
            raise ValueError("Invalid broker extension identifier.")

    @staticmethod
    def _validate_state_key(value: Any, name: str) -> None:
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError(f"Invalid authoritative {name}.")

    @staticmethod
    def _safe_error(exc: Exception) -> tuple[str, str]:
        name = exc.__class__.__name__
        if "Backpressure" in name:
            return "BackpressureError", str(exc)[:500]
        if isinstance(exc, PermissionError):
            return "PermissionError", str(exc)[:500]
        if isinstance(exc, TimeoutError):
            return "TimeoutError", str(exc)[:500]
        if isinstance(exc, ValueError):
            return "ValueError", str(exc)[:500]
        return "RuntimeError", "Authoritative owner operation failed."

    @staticmethod
    def _raise_remote_error(error_type: str, message: str) -> None:
        if error_type == "PermissionError":
            raise PermissionError(message)
        if error_type == "TimeoutError":
            raise TimeoutError(message)
        if error_type == "BackpressureError":
            raise BrokerBackpressureError(message)
        if error_type == "ValueError":
            raise ValueError(message)
        raise RuntimeError(message or "Authoritative owner operation failed.")


@dataclass
class _ModuleConfig:
    broker: EphemeralBroker = field(default_factory=EphemeralBroker)


_module_config = _ModuleConfig()


def configure(handler: Handler) -> None:
    _module_config.broker.configure(handler)


def in_handler() -> bool:
    return _handler_context.get() is not None


async def call(
    extension_id: str,
    operation: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 2.0,
) -> dict[str, Any]:
    return await _module_config.broker.call(
        extension_id, operation, payload, timeout_seconds=timeout_seconds
    )


def check_owner(extension_id: str) -> bool:
    return _module_config.broker.check_owner(extension_id)


def is_owner(extension_id: str) -> bool:
    return _module_config.broker.is_owner(extension_id)


def epoch(extension_id: str) -> int:
    return _module_config.broker.epoch(extension_id)


async def assert_owner(extension_id: str, conn: Any = None) -> int:
    return await _module_config.broker.assert_owner(extension_id, conn)


async def invalidate(extension_id: str) -> None:
    await _module_config.broker.invalidate(extension_id)


def publish_state(
    extension_id: str,
    room_id: str,
    owner_id: str,
    state: dict[str, Any],
    generation: str,
    *,
    max_rooms: int = _DEFAULT_STATE_ROOMS,
) -> None:
    _module_config.broker.publish_state(
        extension_id,
        room_id,
        owner_id,
        state,
        generation,
        max_rooms=max_rooms,
    )


async def recover_state(
    extension_id: str, room_id: str, owner_id: str
) -> dict[str, Any] | None:
    return await _module_config.broker.recover_state(extension_id, room_id, owner_id)
