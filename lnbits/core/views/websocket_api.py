from fastapi import APIRouter, WebSocket

from ..services import websocket_manager

websocket_router = APIRouter(prefix="/api/v1/ws", tags=["Websocket"])


@websocket_router.websocket("/{item_id}")
async def websocket_connect(websocket: WebSocket, item_id: str) -> None:
    conn = await websocket_manager.connect(item_id, websocket)
    await websocket_manager.listen(conn)


@websocket_router.post("/{item_id}")
async def websocket_update_post(item_id: str, data: str):
    try:
        await websocket_manager.send(item_id, data)
        return {"sent": True, "data": data}
    except Exception:
        return {"sent": False, "data": data}


@websocket_router.get("/{item_id}/{data}")
async def websocket_update_get(item_id: str, data: str):
    try:
        await websocket_manager.send(item_id, data)
        return {"sent": True, "data": data}
    except Exception:
        return {"sent": False, "data": data}
