from __future__ import annotations

import asyncio
import json
import math
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from lnbits.settings import settings

from .authoritative_channels import (
    AuthoritativeChannelBackpressureError,
    get_authoritative_channel_generation,
    get_authoritative_channel_state,
    get_authoritative_principal_sequence,
    release_authoritative_connection,
    renew_authoritative_connection,
    reserve_authoritative_connection,
    run_authoritative_channel_export,
    validate_authoritative_channel_limits,
    wait_authoritative_channel_state_change,
)

if TYPE_CHECKING:
    from lnbits.core.wasm_ext.wasm.loader import WasmExtension

_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_LOCAL_ITEM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$")
_ROLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
WEBSOCKET_PUBLISH_MAX_MESSAGES_PER_SECOND_LIMIT = 100
WEBSOCKET_CLIENT_MAX_MESSAGES_PER_SECOND = 60
WEBSOCKET_CLIENT_MAX_MESSAGE_BYTES = 8192
_MAX_CLIENT_SEQUENCE = 2**63 - 1
_AUTHORITATIVE_OUTGOING_QUEUE_DEPTH = 64
_AUTHORITATIVE_CLOSE_TIMEOUT_SECONDS = 1


@dataclass
class WasmExtensionWebsocketConnection:
    extension_id: str
    item_id: str
    websocket: WebSocket


@dataclass
class WasmAuthoritativeChannelConnection:
    extension: WasmExtension
    room_id: str
    websocket: WebSocket
    owner_id: str
    principal_id: str
    role: str
    can_send: bool
    connection_id: str
    limits: dict[str, int]
    last_client_sequence: int
    permissions: list[Any]
    last_received_sequence: int = 0
    room_generation: str | None = None
    policy_generation: int | None = None
    outgoing: asyncio.Queue[str] | None = None
    sender_task: asyncio.Task[None] | None = None
    incoming: asyncio.Queue[tuple[int, dict[str, Any], int] | None] | None = None
    reject_incoming: bool = False


class WasmExtensionWebsocketRateLimitError(PermissionError):
    pass


def scoped_websocket_item_id(extension_id: str, item_id: str) -> str:
    if not _EXTENSION_ID_RE.fullmatch(extension_id):
        raise ValueError("Extension websocket namespace is invalid.")
    if not _LOCAL_ITEM_ID_RE.fullmatch(item_id):
        raise ValueError(
            "Extension websocket item ID must be 1-128 characters and contain "
            "only letters, numbers, colon, underscore, or dash."
        )
    return f"ext:{extension_id}:{item_id}"


class WasmExtensionWebsocketHub:
    def __init__(self) -> None:
        self.active_connections: list[WasmExtensionWebsocketConnection] = []
        self.publish_timestamps: dict[tuple[str, str], deque[float]] = {}
        self.client_timestamps: dict[int, deque[float]] = {}
        self.authoritative_connections: list[WasmAuthoritativeChannelConnection] = []
        self.authoritative_event_timestamps: dict[tuple[str, str], deque[float]] = {}
        self.authoritative_tasks: dict[
            tuple[str, str], tuple[asyncio.Task[None], ...]
        ] = {}
        self.closing_tasks: set[asyncio.Task[None]] = set()

    async def connect(
        self, extension_id: str, item_id: str, websocket: WebSocket
    ) -> WasmExtensionWebsocketConnection:
        scoped_websocket_item_id(extension_id, item_id)
        logger.debug(f"WASM websocket connected to {extension_id}:{item_id}")
        await websocket.accept()
        conn = WasmExtensionWebsocketConnection(
            extension_id=extension_id,
            item_id=item_id,
            websocket=websocket,
        )
        self.active_connections.append(conn)
        return conn

    async def listen(self, conn: WasmExtensionWebsocketConnection) -> None:
        while settings.lnbits_running:
            try:
                data = await conn.websocket.receive_text()
                if len(data.encode()) > WEBSOCKET_CLIENT_MAX_MESSAGE_BYTES:
                    await conn.websocket.close(code=1009)
                    self.disconnect(conn)
                    break
                self._check_client_rate(conn)
                await self._broadcast_client_message(conn, data)
            except WebSocketDisconnect:
                self.disconnect(conn)
                break
            except WasmExtensionWebsocketRateLimitError:
                await conn.websocket.close(code=1008)
                self.disconnect(conn)
                break

    async def serve_authoritative_channel(  # noqa: C901
        self,
        extension: WasmExtension,
        room_id: str,
        websocket: WebSocket,
        *,
        owner_id: str,
        limits: dict[str, int],
        permissions: list[Any] | None = None,
        policy_generation: int | None = None,
    ) -> None:
        channel = extension.config.authoritative_channel
        if not channel:
            await self._close(websocket, 1008)
            return
        if getattr(channel, "persistence", "durable") == "ephemeral" and (
            permissions is None or policy_generation is None
        ):
            await self._close(websocket, 1008)
            return
        try:
            scoped_websocket_item_id(extension.id, room_id)
            validate_authoritative_channel_limits(channel, limits)
        except (TypeError, ValueError):
            await self._close(websocket, 1008)
            return

        connection_id = uuid4().hex
        try:
            slot_reserved = await reserve_authoritative_connection(
                extension.id,
                room_id,
                owner_id,
                connection_id,
                max_active_rooms=channel.max_active_rooms,
                max_connections_per_room=limits[
                    "wasm_runtime_max_authoritative_connections_per_room"
                ],
                persistence=getattr(channel, "persistence", "durable"),
            )
        except PermissionError:
            await self._close(websocket, 1008)
            return
        if not slot_reserved:
            await self._close(websocket, 1013)
            return

        conn: WasmAuthoritativeChannelConnection | None = None
        try:
            await websocket.accept()
            token = await self._receive_authorization_token(websocket)
            conn, state = await self._authorize_authoritative_connection(
                extension,
                room_id,
                websocket,
                owner_id,
                limits,
                token,
                connection_id,
                permissions or [],
                policy_generation,
            )
            self.authoritative_connections.append(conn)
            slot_reserved = False
            self._start_authoritative_sender(conn)
            await self._send_authoritative(
                conn,
                json.dumps(
                    {
                        "type": "snapshot",
                        "state": state.snapshot,
                        "sequence": state.sequence,
                        "lastClientSequence": conn.last_client_sequence,
                        **(
                            {"roomGeneration": conn.room_generation}
                            if conn.room_generation
                            else {}
                        ),
                    }
                ),
            )
            self._start_authoritative_room_tasks(conn, state.version)
            await self.listen_authoritative_channel(conn)
        except WebSocketDisconnect:
            pass
        except AuthoritativeChannelBackpressureError:
            await self._close(websocket, 1013)
        except (ValueError, PermissionError, asyncio.TimeoutError):
            await self._close(websocket, 1008)
        except Exception as exc:
            logger.warning(
                f"WASM authoritative websocket failed for {extension.id}:{room_id} "
                f"({exc.__class__.__name__})."
            )
            await self._close(websocket, 1011)
        finally:
            if slot_reserved:
                await release_authoritative_connection(
                    extension.id,
                    connection_id,
                    room_id=room_id,
                    persistence=getattr(channel, "persistence", "durable"),
                )
            if conn:
                await self.disconnect_authoritative(conn)

    async def _authorize_authoritative_connection(
        self,
        extension: WasmExtension,
        room_id: str,
        websocket: WebSocket,
        owner_id: str,
        limits: dict[str, int],
        token: str,
        connection_id: str,
        permissions: list[Any],
        policy_generation: int | None,
    ) -> tuple[WasmAuthoritativeChannelConnection, Any]:
        channel = extension.config.authoritative_channel
        assert channel
        persistence = getattr(channel, "persistence", "durable")
        result = await run_authoritative_channel_export(
            extension,
            room_id,
            owner_id,
            channel.authorize_connection,
            {"roomId": room_id, "sessionToken": token},
            limits=limits,
            action="authorize",
            permissions=permissions if persistence == "ephemeral" else None,
            policy_generation=policy_generation,
        )
        data = result.get("data") if isinstance(result, dict) else None
        principal_id = data.get("principalId") if isinstance(data, dict) else None
        role = data.get("role", "member") if isinstance(data, dict) else None
        can_send = data.get("canSend") if isinstance(data, dict) else None
        if (
            not isinstance(principal_id, str)
            or not principal_id
            or len(principal_id) > 256
            or any(ord(char) < 32 for char in principal_id)
            or not isinstance(role, str)
            or not _ROLE_RE.fullmatch(role)
            or not isinstance(can_send, bool)
        ):
            raise PermissionError("Channel authorization failed.")
        state = await get_authoritative_channel_state(
            extension.id,
            room_id,
            owner_id,
            max_bytes=limits["wasm_runtime_max_authoritative_state_bytes"],
            persistence=persistence,
        )
        if not state.has_snapshot:
            raise PermissionError("Channel did not provide a canonical snapshot.")
        last_client_sequence = (
            await get_authoritative_principal_sequence(
                extension.id,
                room_id,
                principal_id,
                persistence=persistence,
            )
            if can_send
            else 0
        )
        return (
            WasmAuthoritativeChannelConnection(
                extension=extension,
                room_id=room_id,
                websocket=websocket,
                owner_id=owner_id,
                principal_id=principal_id,
                role=role,
                can_send=can_send,
                connection_id=connection_id,
                limits=limits,
                last_client_sequence=last_client_sequence,
                permissions=permissions,
                last_received_sequence=last_client_sequence,
                room_generation=(
                    get_authoritative_channel_generation(
                        extension.id, room_id, owner_id
                    )
                    if persistence == "ephemeral"
                    else None
                ),
                policy_generation=policy_generation,
            ),
            state,
        )

    async def listen_authoritative_channel(  # noqa: C901
        self, conn: WasmAuthoritativeChannelConnection
    ) -> None:
        channel = conn.extension.config.authoritative_channel
        assert channel
        incoming: asyncio.Queue[tuple[int, dict[str, Any], int] | None] = asyncio.Queue(
            maxsize=min(channel.max_queue_depth, 64)
        )
        conn.incoming = incoming
        processor = asyncio.create_task(
            self._process_authoritative_events(conn, incoming)
        )
        try:
            while settings.lnbits_running:
                frame = await conn.websocket.receive_text()
                received_at_ns = time.monotonic_ns()
                if len(frame.encode()) > WEBSOCKET_CLIENT_MAX_MESSAGE_BYTES:
                    await self._close(conn.websocket, 1009)
                    return
                self._check_authoritative_client_rate(conn)
                request = _strict_json_loads(frame)
                expected_fields = {"sequence", "event"}
                if conn.room_generation:
                    expected_fields.add("roomGeneration")
                if (
                    not isinstance(request, dict)
                    or set(request) != expected_fields
                    or (
                        conn.room_generation
                        and request.get("roomGeneration") != conn.room_generation
                    )
                ):
                    await self._close(conn.websocket, 1008)
                    return
                sequence = request["sequence"]
                event = request["event"]
                if (
                    not conn.can_send
                    or channel.on_event is None
                    or isinstance(sequence, bool)
                    or not isinstance(sequence, int)
                    or sequence > _MAX_CLIENT_SEQUENCE
                    or sequence <= conn.last_received_sequence
                    or not isinstance(event, dict)
                    or not all(isinstance(key, str) for key in event)
                    or not set(event).issubset(channel.event_fields)
                    or not all(_valid_event_value(value) for value in event.values())
                ):
                    await self._close(conn.websocket, 1008)
                    return
                conn.last_received_sequence = sequence
                try:
                    incoming.put_nowait((sequence, event, received_at_ns))
                except asyncio.QueueFull:
                    conn.reject_incoming = True
                    await self._send_rejected_event(conn, sequence)
                    await self._close(conn.websocket, 1013)
                    return
        except WebSocketDisconnect:
            return
        except (ValueError, UnicodeDecodeError, RecursionError):
            await self._close(conn.websocket, 1008)
        except WasmExtensionWebsocketRateLimitError:
            await self._close(conn.websocket, 1008)
        finally:
            if not processor.done():
                await incoming.put(None)
            await asyncio.gather(processor, return_exceptions=True)

    async def _process_authoritative_events(
        self,
        conn: WasmAuthoritativeChannelConnection,
        incoming: asyncio.Queue[tuple[int, dict[str, Any], int] | None],
    ) -> None:
        channel = conn.extension.config.authoritative_channel
        assert channel
        persistence = getattr(channel, "persistence", "durable")
        while True:
            item = await incoming.get()
            if item is None:
                incoming.task_done()
                return
            sequence, event, received_at_ns = item
            try:
                if conn.reject_incoming:
                    await self._send_rejected_event(conn, sequence)
                    continue
                result = await run_authoritative_channel_export(
                    conn.extension,
                    conn.room_id,
                    conn.owner_id,
                    channel.on_event or "",
                    {"event": event, "principalRole": conn.role},
                    limits=conn.limits,
                    action="event",
                    principal_id=conn.principal_id,
                    client_sequence=sequence,
                    connection_id=conn.connection_id,
                    received_at_ns=received_at_ns,
                    room_generation=conn.room_generation,
                    permissions=(
                        conn.permissions if persistence == "ephemeral" else None
                    ),
                    policy_generation=conn.policy_generation,
                )
                conn.last_client_sequence = sequence
                await self._send_authoritative(
                    conn,
                    json.dumps(
                        {
                            "type": "eventAccepted",
                            "clientSequence": sequence,
                            "sequence": result.pop("_hostSequence"),
                        }
                    ),
                )
            except AuthoritativeChannelBackpressureError:
                conn.reject_incoming = True
                await self._send_rejected_event(conn, sequence)
                await self._close(conn.websocket, 1013)
            except Exception as exc:
                logger.warning(
                    f"WASM authoritative event failed for "
                    f"{conn.extension.id}:{conn.room_id} "
                    f"({exc.__class__.__name__})."
                )
                await self._send_rejected_event(conn, sequence)
            finally:
                incoming.task_done()

    async def _send_rejected_event(
        self, conn: WasmAuthoritativeChannelConnection, sequence: int
    ) -> None:
        await self._send_authoritative(
            conn,
            json.dumps({"type": "eventRejected", "clientSequence": sequence}),
        )

    async def disconnect_authoritative(
        self, conn: WasmAuthoritativeChannelConnection
    ) -> None:
        channel = conn.extension.config.authoritative_channel
        persistence = (
            getattr(channel, "persistence", "durable") if channel else "durable"
        )
        await release_authoritative_connection(
            conn.extension.id,
            conn.connection_id,
            room_id=conn.room_id,
            persistence=persistence,
        )
        self.authoritative_connections = [
            active
            for active in self.authoritative_connections
            if active.websocket != conn.websocket
        ]
        sender_task = conn.sender_task
        conn.sender_task = None
        conn.outgoing = None
        if sender_task and sender_task is not asyncio.current_task():
            sender_task.cancel()
            await asyncio.gather(sender_task, return_exceptions=True)
        key = (conn.extension.id, conn.room_id)
        if not any(
            (active.extension.id, active.room_id) == key
            for active in self.authoritative_connections
        ):
            self.authoritative_event_timestamps.pop(key, None)
            tasks = self.authoritative_tasks.pop(key, None)
            if tasks:
                for task in tasks:
                    if task is not asyncio.current_task():
                        task.cancel()

    async def close_ephemeral_extension(self, extension_id: str) -> None:
        connections = [
            conn
            for conn in self.authoritative_connections
            if conn.extension.id == extension_id
            and conn.extension.config.authoritative_channel
            and getattr(
                conn.extension.config.authoritative_channel, "persistence", "durable"
            )
            == "ephemeral"
        ]
        for conn in connections:
            await self._close(conn.websocket, 1008)
            await self.disconnect_authoritative(conn)

    def _start_authoritative_room_tasks(
        self,
        conn: WasmAuthoritativeChannelConnection,
        state_version: int,
    ) -> None:
        key = (conn.extension.id, conn.room_id)
        if key in self.authoritative_tasks:
            return
        tasks = [
            asyncio.create_task(
                self._broadcast_authoritative_state(conn, state_version)
            )
        ]
        channel = conn.extension.config.authoritative_channel
        if channel and getattr(channel, "persistence", "durable") == "durable":
            tasks.append(
                asyncio.create_task(self._renew_authoritative_connections(conn))
            )
        if channel and channel.on_schedule and channel.schedule_interval_ms:
            tasks.append(asyncio.create_task(self._run_authoritative_schedule(conn)))
        self.authoritative_tasks[key] = tuple(tasks)

    async def _renew_authoritative_connections(
        self, conn: WasmAuthoritativeChannelConnection
    ) -> None:
        try:
            while settings.lnbits_running and self._has_authoritative_room(conn):
                await asyncio.sleep(60)
                for active in self.get_authoritative_connections(
                    conn.extension.id, conn.room_id
                ):
                    renewed = await renew_authoritative_connection(
                        active.extension.id, active.room_id, active.connection_id
                    )
                    if not renewed:
                        await self._close(active.websocket, 1013)
        except asyncio.CancelledError:
            return

    async def _run_authoritative_schedule(
        self, conn: WasmAuthoritativeChannelConnection
    ) -> None:
        channel = conn.extension.config.authoritative_channel
        if not channel or not channel.on_schedule or not channel.schedule_interval_ms:
            return
        try:
            while settings.lnbits_running and self._has_authoritative_room(conn):
                await asyncio.sleep(channel.schedule_interval_ms / 1000)
                try:
                    await run_authoritative_channel_export(
                        conn.extension,
                        conn.room_id,
                        conn.owner_id,
                        channel.on_schedule,
                        {},
                        limits=conn.limits,
                        action="schedule",
                        room_generation=conn.room_generation,
                        permissions=(
                            conn.permissions
                            if getattr(channel, "persistence", "durable") == "ephemeral"
                            else None
                        ),
                        policy_generation=conn.policy_generation,
                    )
                except AuthoritativeChannelBackpressureError:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(
                        f"WASM authoritative schedule failed for "
                        f"{conn.extension.id}:{conn.room_id} "
                        f"({exc.__class__.__name__})."
                    )
        except asyncio.CancelledError:
            return

    async def _broadcast_authoritative_state(
        self,
        conn: WasmAuthoritativeChannelConnection,
        last_version: int,
    ) -> None:
        channel = conn.extension.config.authoritative_channel
        assert channel
        interval = min(
            0.25,
            max(0.05, (channel.schedule_interval_ms or 250) / 1000),
        )
        try:
            while settings.lnbits_running and self._has_authoritative_room(conn):
                try:
                    if getattr(channel, "persistence", "durable") == "ephemeral":
                        state = await wait_authoritative_channel_state_change(
                            conn.extension.id,
                            conn.room_id,
                            conn.owner_id,
                            last_version,
                            max_bytes=conn.limits[
                                "wasm_runtime_max_authoritative_state_bytes"
                            ],
                        )
                        if state is None:
                            return
                    else:
                        await asyncio.sleep(interval)
                        state = await get_authoritative_channel_state(
                            conn.extension.id,
                            conn.room_id,
                            conn.owner_id,
                            max_bytes=conn.limits[
                                "wasm_runtime_max_authoritative_state_bytes"
                            ],
                        )
                except Exception as exc:
                    logger.warning(
                        f"WASM authoritative state sync failed for "
                        f"{conn.extension.id}:{conn.room_id} "
                        f"({exc.__class__.__name__})."
                    )
                    continue
                if state.version <= last_version or not state.has_snapshot:
                    continue
                payload = json.dumps(
                    {
                        "type": "state",
                        "state": state.snapshot,
                        "sequence": state.sequence,
                    },
                    allow_nan=False,
                )
                for active in self.get_authoritative_connections(
                    conn.extension.id, conn.room_id
                ):
                    await self._send_authoritative(active, payload)
                last_version = state.version
        except asyncio.CancelledError:
            return

    def _has_authoritative_room(self, conn: WasmAuthoritativeChannelConnection) -> bool:
        return any(
            (active.extension.id, active.room_id) == (conn.extension.id, conn.room_id)
            for active in self.authoritative_connections
        )

    def get_authoritative_connections(
        self, extension_id: str, room_id: str
    ) -> list[WasmAuthoritativeChannelConnection]:
        return [
            conn
            for conn in self.authoritative_connections
            if conn.extension.id == extension_id and conn.room_id == room_id
        ]

    async def _receive_authorization_token(self, websocket: WebSocket) -> str:
        frame = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        if len(frame.encode()) > 2048:
            raise ValueError("WASM channel authorization message is too large.")
        message = _strict_json_loads(frame)
        token = message.get("token") if isinstance(message, dict) else None
        if (
            not isinstance(message, dict)
            or set(message) != {"type", "token"}
            or message.get("type") != "authorize"
            or not isinstance(token, str)
            or not token
            or len(token) > 1024
        ):
            raise ValueError("WASM channel authorization message is invalid.")
        return token

    def _check_authoritative_client_rate(
        self, conn: WasmAuthoritativeChannelConnection
    ) -> None:
        now = time.monotonic()
        key = (conn.extension.id, conn.room_id)
        timestamps = self.authoritative_event_timestamps.setdefault(key, deque())
        while timestamps and now - timestamps[0] >= 1:
            timestamps.popleft()
        channel = conn.extension.config.authoritative_channel
        if not channel or len(timestamps) >= channel.max_events_per_second:
            raise WasmExtensionWebsocketRateLimitError(
                "WASM authoritative channel event rate exceeded."
            )
        timestamps.append(now)

    async def _send_authoritative(
        self, conn: WasmAuthoritativeChannelConnection, data: str
    ) -> bool:
        if not conn.outgoing:
            return False
        try:
            conn.outgoing.put_nowait(data)
            return True
        except asyncio.QueueFull:
            await self.disconnect_authoritative(conn)
            task = asyncio.create_task(self._close(conn.websocket, 1013))
            self.closing_tasks.add(task)
            task.add_done_callback(self.closing_tasks.discard)
            return False

    def _start_authoritative_sender(
        self, conn: WasmAuthoritativeChannelConnection
    ) -> None:
        conn.outgoing = asyncio.Queue(maxsize=_AUTHORITATIVE_OUTGOING_QUEUE_DEPTH)
        conn.sender_task = asyncio.create_task(self._send_authoritative_queue(conn))

    async def _send_authoritative_queue(
        self, conn: WasmAuthoritativeChannelConnection
    ) -> None:
        outgoing = conn.outgoing
        assert outgoing is not None
        try:
            while True:
                data = await outgoing.get()
                try:
                    await conn.websocket.send_text(data)
                finally:
                    outgoing.task_done()
        except (RuntimeError, WebSocketDisconnect):
            await self.disconnect_authoritative(conn)
        except asyncio.CancelledError:
            return

    async def _close(self, websocket: WebSocket, code: int) -> None:
        try:
            await asyncio.wait_for(
                websocket.close(code=code), timeout=_AUTHORITATIVE_CLOSE_TIMEOUT_SECONDS
            )
        except (RuntimeError, WebSocketDisconnect, asyncio.TimeoutError):
            pass

    def disconnect(self, conn: WasmExtensionWebsocketConnection) -> None:
        self.active_connections = [
            active_conn
            for active_conn in self.active_connections
            if active_conn.websocket != conn.websocket
        ]
        self.client_timestamps.pop(id(conn.websocket), None)
        logger.debug(
            f"WASM websocket disconnected from {conn.extension_id}:{conn.item_id}"
        )

    def get_connections(
        self, extension_id: str, item_id: str
    ) -> list[WasmExtensionWebsocketConnection]:
        return [
            conn
            for conn in self.active_connections
            if conn.extension_id == extension_id and conn.item_id == item_id
        ]

    async def publish(
        self,
        extension_id: str,
        item_id: str,
        data: str,
        *,
        max_messages_per_second: int,
    ) -> None:
        scoped_websocket_item_id(extension_id, item_id)
        self._check_publish_rate(
            extension_id,
            item_id,
            max_messages_per_second=max_messages_per_second,
        )
        for conn in self.get_connections(extension_id, item_id):
            await self._send_to_connection(conn, data)

    def _check_publish_rate(
        self,
        extension_id: str,
        item_id: str,
        *,
        max_messages_per_second: int,
    ) -> None:
        if (
            isinstance(max_messages_per_second, bool)
            or not isinstance(max_messages_per_second, int)
            or max_messages_per_second <= 0
            or max_messages_per_second > WEBSOCKET_PUBLISH_MAX_MESSAGES_PER_SECOND_LIMIT
        ):
            raise ValueError("Invalid websocket publish rate limit.")

        now = time.monotonic()
        channel = (extension_id, item_id)
        timestamps = self.publish_timestamps.setdefault(channel, deque())
        while timestamps and now - timestamps[0] >= 1:
            timestamps.popleft()
        if len(timestamps) >= max_messages_per_second:
            raise WasmExtensionWebsocketRateLimitError(
                "WASM websocket publish rate limit exceeded."
            )
        timestamps.append(now)

    def _check_client_rate(self, conn: WasmExtensionWebsocketConnection) -> None:
        now = time.monotonic()
        key = id(conn.websocket)
        timestamps = self.client_timestamps.setdefault(key, deque())
        while timestamps and now - timestamps[0] >= 1:
            timestamps.popleft()
        if len(timestamps) >= WEBSOCKET_CLIENT_MAX_MESSAGES_PER_SECOND:
            raise WasmExtensionWebsocketRateLimitError(
                "WASM websocket client rate limit exceeded."
            )
        timestamps.append(now)

    async def _broadcast_client_message(
        self,
        conn: WasmExtensionWebsocketConnection,
        data: str,
    ) -> None:
        for active_conn in self.get_connections(conn.extension_id, conn.item_id):
            if active_conn.websocket == conn.websocket:
                continue
            await self._send_to_connection(active_conn, data)

    async def _send_to_connection(
        self,
        conn: WasmExtensionWebsocketConnection,
        data: str,
    ) -> None:
        try:
            await conn.websocket.send_text(data)
        except (RuntimeError, WebSocketDisconnect):
            self.disconnect(conn)


wasm_extension_websocket_hub = WasmExtensionWebsocketHub()


def _strict_json_loads(value: str) -> Any:
    def reject_constant(constant: str) -> None:
        raise ValueError(f"Invalid JSON constant: {constant}")

    return json.loads(value, parse_constant=reject_constant)


def _valid_event_value(value: Any, depth: int = 0) -> bool:
    if depth > 8:
        return False
    value_type = type(value)
    if value is None or value_type is bool:
        return True
    if value_type is int:
        return abs(value) <= (2**53 - 1)
    if value_type is float:
        return math.isfinite(value)
    if value_type is str:
        return True
    if value_type is list:
        return all(_valid_event_value(item, depth + 1) for item in value)
    if value_type is dict:
        return all(
            isinstance(key, str) and _valid_event_value(item, depth + 1)
            for key, item in value.items()
        )
    return False
