from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)

from ..services import (
    websocketManager,
    websocketUpdater,
)

websocket_router = APIRouter(prefix="/api/v1/ws", tags=["Websocket"])


@websocket_router.websocket("/{item_id}")
async def websocket_connect(websocket: WebSocket, item_id: str):
    await websocketManager.connect(websocket, item_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocketManager.disconnect(websocket)


@websocket_router.post("/{item_id}")
async def websocket_update_post(item_id: str, data: str):
    try:
        await websocketUpdater(item_id, data)
        return {"sent": True, "data": data}
    except Exception:
        return {"sent": False, "data": data}


@websocket_router.get("/{item_id}/{data}")
async def websocket_update_get(item_id: str, data: str):
    try:
        await websocketUpdater(item_id, data)
        return {"sent": True, "data": data}
    except Exception:
        return {"sent": False, "data": data}
