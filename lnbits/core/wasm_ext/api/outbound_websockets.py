from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from uuid import uuid4

import httpx
from loguru import logger
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from lnbits.core.crud.extensions import get_installed_extension, get_user_extension
from lnbits.core.crud.users import get_account
from lnbits.core.db import core_app_extra
from lnbits.core.models.extensions import InstallableExtension
from lnbits.core.models.users import Account
from lnbits.settings import settings
from lnbits.utils.safe_http import safe_websocket


@dataclass
class OutboundConnection:
    extension_id: str
    user_id: str | None
    url: str
    name: str | None
    id: str = field(default_factory=lambda: uuid4().hex)
    ready: asyncio.Future[bool] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )
    socket: ClientConnection | None = None
    task: asyncio.Task[None] = field(init=False, repr=False)
    waiters: int = 0
    claimed: bool = False
    slot_released: bool = False

    def release_slot(self) -> None:
        self.slot_released = True


class OutboundWebsockets:
    def __init__(self) -> None:
        self.connections: dict[str, OutboundConnection] = {}

    async def open(
        self, extension_id: str, user_id: str | None, url: str, name: str | None
    ) -> str:
        from lnbits.core.services.extensions import resolve_wasm_runtime_limits

        try:
            target = httpx.URL(url)
        except httpx.InvalidURL:
            raise ValueError("Invalid WebSocket URL.") from None
        if (
            target.scheme != "wss"
            or not target.host
            or target.userinfo
            or target.fragment
        ):
            raise ValueError(
                "WebSockets require a wss:// URL without credentials or a fragment."
            )
        url = str(target)
        installed, _, _ = await _check_access(extension_id, user_id)
        # All reservations run on the host event loop. Keep lookup, quota check and
        # insertion together before the first await so concurrent opens share a slot.
        live = [
            c
            for c in self.connections.values()
            if not c.slot_released and not c.task.done()
        ]
        extension_connections = [c for c in live if c.extension_id == extension_id]
        owned = [c for c in extension_connections if c.user_id == user_id]
        conn = next(
            (
                c
                for c in owned
                if name is not None
                and c.name == name
                and (not c.ready.done() or (c.socket and c.socket.close_code is None))
            ),
            None,
        )
        if conn:
            if conn.url != url:
                raise ValueError(
                    "WebSocket name already belongs to a different destination."
                )
        else:
            limits = resolve_wasm_runtime_limits(installed)
            per_user = limits["wasm_runtime_max_websockets_per_user"]
            per_extension = limits["wasm_runtime_max_websockets_per_extension"]
            if (
                len(live) >= settings.lnbits_wasm_max_websockets
                or (per_extension and len(extension_connections) >= per_extension)
                or (per_user and len(owned) >= per_user)
            ):
                raise ValueError("Outbound WebSocket connection limit reached.")
            conn = OutboundConnection(extension_id, user_id, url, name)
            conn.task = asyncio.create_task(self._listen(conn))
            self.connections[conn.id] = conn
            conn.task.add_done_callback(partial(self._discard, conn))

        conn.waiters += 1
        try:
            if not await asyncio.shield(conn.ready):
                raise ValueError("Outbound WebSocket could not be opened.")
            conn.claimed = True
            return conn.id
        finally:
            conn.waiters -= 1
            # A cancelled caller must not strand a socket or cancel another
            # caller's pending handshake for the same name.
            if not conn.waiters and not conn.claimed and not conn.task.done():
                conn.release_slot()
                conn.task.cancel()
                await asyncio.gather(conn.task, return_exceptions=True)

    async def send(
        self, extension_id: str, user_id: str | None, connection_id: str, text: str
    ) -> None:
        socket = await self._owned_socket(extension_id, user_id, connection_id)
        try:
            await socket.send(text)
        except ConnectionClosed:
            raise ValueError("Outbound WebSocket is closed.") from None

    async def close(
        self, extension_id: str, user_id: str | None, connection_id: str
    ) -> None:
        socket = await self._owned_socket(extension_id, user_id, connection_id)
        await socket.close()

    async def stop(
        self, extension_id: str | None = None, user_id: str | None = None
    ) -> None:
        await self._cancel(
            [
                c.task
                for c in self.connections.values()
                if (extension_id is None or c.extension_id == extension_id)
                and (user_id is None or c.user_id == user_id)
            ]
        )

    async def apply_admin_settings(self) -> None:
        denied = []
        for conn in list(self.connections.values()):
            if (
                settings.lnbits_extensions_deactivate_all
                or not settings.is_admin_extension(conn.extension_id)
            ):
                denied.append(conn.task)
            elif conn.user_id and not settings.is_admin_user(conn.user_id):
                entry = await get_user_extension(conn.user_id, conn.extension_id)
                if not entry or not entry.active or not entry.admin_access_granted:
                    denied.append(conn.task)
        await self._cancel(denied)

    async def _cancel(self, tasks: list[asyncio.Task[None]]) -> None:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _owned_socket(
        self, extension_id: str, user_id: str | None, connection_id: str
    ) -> ClientConnection:
        await _check_access(extension_id, user_id)
        conn = self.connections.get(connection_id)
        if (
            not conn
            or conn.extension_id != extension_id
            or conn.user_id != user_id
            or not conn.socket
        ):
            raise ValueError("Unknown outbound WebSocket connection.")
        return conn.socket

    async def _listen(self, conn: OutboundConnection) -> None:
        code, reason = 1006, "Connection lost"
        try:
            # Recheck after reservation so disablement also covers in-flight opens.
            await _check_access(conn.extension_id, conn.user_id)
            async with safe_websocket(conn.url, apply_callback_rules=False) as socket:
                conn.socket = socket
                conn.ready.set_result(True)
                try:
                    while settings.lnbits_running:
                        message = await socket.recv()
                        if not isinstance(message, str):
                            code, reason = 1003, "Unsupported binary message"
                            await socket.close(code, reason)
                            break
                        await _dispatch(conn, {"type": "message", "text": message})
                except ConnectionClosed:
                    code, reason = socket.close_code or 1006, socket.close_reason or ""
                except PermissionError:
                    code, reason = 1008, "Access denied"
                    await socket.close(code, reason)
                except Exception:
                    code, reason = 1011, "WebSocket callback failed"
                    await socket.close(code, reason)
        except Exception as exc:
            # Transport errors can contain credentials from URL queries.
            logger.debug("WASM WebSocket {} failed ({})", conn.id, type(exc).__name__)
        finally:
            conn.socket = None

        if conn.ready.done() and settings.lnbits_running:
            try:
                await _dispatch(
                    conn, {"type": "closed", "code": code, "reason": reason}
                )
            except Exception as exc:
                logger.debug(
                    "WASM WebSocket {} close callback failed ({})",
                    conn.id,
                    type(exc).__name__,
                )

    def _discard(self, conn: OutboundConnection, _task: asyncio.Task) -> None:
        self.connections.pop(conn.id, None)
        if not conn.ready.done():
            conn.ready.set_result(False)


outbound_websockets = OutboundWebsockets()


async def _check_access(
    extension_id: str, user_id: str | None
) -> tuple[InstallableExtension, Account | None, str]:
    installed = await get_installed_extension(extension_id)
    extension = core_app_extra.wasm_extension_registry.get(extension_id)
    handler = extension.config.events.on_websocket if extension else None
    if (
        not settings.lnbits_running
        or settings.lnbits_extensions_deactivate_all
        or not installed
        or not installed.active
        or not installed.is_admin_only
        or not any(p.id == "websocket.connect" for p in installed.permissions)
        or not handler
    ):
        raise PermissionError(
            "Outbound WebSockets require an active, approved admin-only extension."
        )
    if user_id is None:
        return installed, None, handler
    account = await get_account(user_id)
    enabled = await get_user_extension(user_id, extension_id)
    if (
        not account
        or not account.activated
        or not installed.is_available_for_user(user_id, enabled)
        or not enabled
        or not enabled.active
    ):
        raise PermissionError("WebSocket owner no longer has access.")
    return installed, account, handler


async def _dispatch(conn: OutboundConnection, event: dict[str, Any]) -> None:
    from lnbits.core.services.extensions import WasmInvocationCapacityError

    from ..wasm.invoke import invoke_wasm_extension_export

    while settings.lnbits_running:
        _, user, handler = await _check_access(conn.extension_id, conn.user_id)
        try:
            await invoke_wasm_extension_export(
                conn.extension_id,
                handler,
                {"connectionId": conn.id, **event},
                user=user,
                owner_id=None if user else f"extension:{conn.extension_id}",
                context="websocket",
                trigger_type="websocket",
                event_type=event["type"],
                # Bound pending close notices by the socket quota. Once admitted,
                # the close handler can use this slot to open its replacement.
                on_admitted=conn.release_slot if event["type"] == "closed" else None,
            )
            return
        except WasmInvocationCapacityError as exc:
            # The listener holds this event and reads the next only after delivery.
            await exc.capacity_changed.wait()
    raise PermissionError("LNbits is shutting down.")
