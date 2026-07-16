from fastapi import APIRouter, WebSocket, status

from lnbits.core.crud import get_installed_extension
from lnbits.core.wasm_ext.api.websockets import wasm_extension_websocket_hub

extension_websocket_router = APIRouter(
    prefix="/api/v1/ext/ws",
    tags=["Extension Websocket"],
)


@extension_websocket_router.websocket("/{ext_id}/{item_id}")
async def extension_websocket_connect(
    websocket: WebSocket,
    ext_id: str,
    item_id: str,
) -> None:
    installed_ext = await get_installed_extension(ext_id)
    installed_permission_ids = (
        {permission.id for permission in installed_ext.permissions or []}
        if installed_ext
        else set()
    )
    if (
        not installed_ext
        or not installed_ext.active
        or not installed_ext.is_wasm
        or "websocket.subscribe" not in installed_permission_ids
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        conn = await wasm_extension_websocket_hub.connect(ext_id, item_id, websocket)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await wasm_extension_websocket_hub.listen(conn)
