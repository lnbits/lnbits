from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from lnbits.settings import settings

_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_LOCAL_ITEM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$")
WEBSOCKET_PUBLISH_MAX_MESSAGES_PER_SECOND_LIMIT = 100
WEBSOCKET_CLIENT_MAX_MESSAGES_PER_SECOND = 60
WEBSOCKET_CLIENT_MAX_MESSAGE_BYTES = 8192


@dataclass
class WasmExtensionWebsocketConnection:
    extension_id: str
    item_id: str
    websocket: WebSocket


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
            await conn.websocket.send_text(data)

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
            await active_conn.websocket.send_text(data)


wasm_extension_websocket_hub = WasmExtensionWebsocketHub()
