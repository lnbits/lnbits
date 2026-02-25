from fastapi import APIRouter, WebSocket

from ..crud.wallets import get_wallet_for_key
from ..models import KeyType
from ..services import websocket_manager

websocket_router = APIRouter(prefix="/api/v1/ws", tags=["Websocket"])


@websocket_router.websocket("/{item_id}")
async def websocket_connect(websocket: WebSocket, item_id: str) -> None:
    conn = await websocket_manager.connect(item_id, websocket)
    await websocket_manager.listen(conn)


@websocket_router.websocket("/tag/{tag}")
async def websocket_connect_tag(websocket: WebSocket, tag: str) -> None:
    api_key = websocket.headers.get("X-API-KEY") or websocket.query_params.get(
        "api-key"
    )
    if not api_key:
        await websocket.close(code=4401)
        return

    wallet = await get_wallet_for_key(api_key)
    if not wallet:
        await websocket.close(code=4404)
        return

    key_type = KeyType.admin if wallet.adminkey == api_key else KeyType.invoice
    if key_type not in {KeyType.admin, KeyType.invoice}:
        await websocket.close(code=4403)
        return

    item_id = f"tag:{wallet.id}:{tag}"
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
