from http import HTTPStatus
from typing import List
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists
from .crud import get_copilot

from functools import wraps

from lnbits.decorators import check_user_exists

from . import copilot_ext, copilot_renderer
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from fastapi.param_functions import Query
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
from lnbits.core.models import User
import base64

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

# socket_relay is a list where the control panel or
# lnurl endpoints can leave a message for the compose window


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@copilot_ext.websocket("/copilot/ws/{socket_id}", name="copilot.websocket_by_id")
async def websocket_endpoint(websocket: WebSocket, socket_id: str):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{socket_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{socket_id} left the chat")


async def updater(copilot_id, data, comment):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        return
    manager.broadcast(f"{data + '-' + comment}")
