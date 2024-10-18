from fastapi import WebSocket
from loguru import logger


class WebsocketConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, item_id: str):
        logger.debug(f"Websocket connected to {item_id}")
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_data(self, message: str, item_id: str):
        for connection in self.active_connections:
            if connection.path_params["item_id"] == item_id:
                await connection.send_text(message)


websocket_manager = WebsocketConnectionManager()


async def websocket_updater(item_id: str, data: str):
    return await websocket_manager.send_data(data, item_id)
