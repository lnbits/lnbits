from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from lnbits.settings import settings


@dataclass
class WebsocketConnection:
    item_id: str
    websocket: WebSocket


class WebsocketConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebsocketConnection] = []

    async def connect(self, item_id: str, websocket: WebSocket) -> WebsocketConnection:
        logger.debug(f"Websocket connected to {item_id}")
        await websocket.accept()
        conn = WebsocketConnection(
            item_id=item_id,
            websocket=websocket,
        )
        self.active_connections.append(conn)
        return conn

    async def listen(self, conn: WebsocketConnection) -> None:
        while settings.lnbits_running:
            try:
                # This endpoint only sends notifications. Drain incoming messages
                # so disconnects are detected without retaining client payloads.
                await conn.websocket.receive_text()
            except WebSocketDisconnect:
                for _conn in self.active_connections:
                    if _conn.websocket == conn.websocket:
                        self.active_connections.remove(_conn)
                        logger.debug(f"WS disconnected from {conn.item_id}")
                break  # out of the listen and the fastapi route

    def get_connections(self, item_id: str) -> list[WebsocketConnection]:
        conns = []
        for conn in self.active_connections:
            if conn.item_id == item_id:
                conns.append(conn)
        return conns

    def has_connection(self, item_id: str) -> bool:
        return len(self.get_connections(item_id)) > 0

    async def send(self, item_id: str, data: str) -> None:
        for conn in self.get_connections(item_id):
            await conn.websocket.send_text(data)


websocket_manager = WebsocketConnectionManager()


# deprecated import and use `websocket_manager.send()` instead
async def websocket_updater(item_id: str, data: str) -> None:
    return await websocket_manager.send(item_id, data)
