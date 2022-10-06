from typing import List

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse  # type: ignore

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import copilot_ext, copilot_renderer
from .crud import get_copilot

templates = Jinja2Templates(directory="templates")


@copilot_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return copilot_renderer().TemplateResponse(
        "copilot/index.html", {"request": request, "user": user.dict()}
    )


@copilot_ext.get("/cp/", response_class=HTMLResponse)
async def compose(request: Request):
    return copilot_renderer().TemplateResponse(
        "copilot/compose.html", {"request": request}
    )


@copilot_ext.get("/pn/", response_class=HTMLResponse)
async def panel(request: Request):
    return copilot_renderer().TemplateResponse(
        "copilot/panel.html", {"request": request}
    )


##################WEBSOCKET ROUTES########################


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, copilot_id: str):
        await websocket.accept()
        websocket.id = copilot_id
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, copilot_id: str):
        for connection in self.active_connections:
            if connection.id == copilot_id:
                await connection.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@copilot_ext.websocket("/ws/{copilot_id}", name="copilot.websocket_by_id")
async def websocket_endpoint(websocket: WebSocket, copilot_id: str):
    await manager.connect(websocket, copilot_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def updater(copilot_id, data, comment):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        return
    await manager.send_personal_message(f"{data + '-' + comment}", copilot_id)
