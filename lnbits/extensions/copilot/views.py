from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists
import asyncio
from .crud import get_copilot

from functools import wraps

from lnbits.decorators import check_user_exists

from . import copilot_ext, copilot_renderer
from fastapi import FastAPI, Request, WebSocket
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

connected_websockets = defaultdict(set)


@copilot_ext.websocket("/ws/{id}/")
async def websocket_endpoint(websocket: WebSocket, id: str = Query(None)):
    copilot = await get_copilot(id)
    if not copilot:
        return "", HTTPStatus.FORBIDDEN
    await websocket.accept()
    invoice_queue = asyncio.Queue()
    connected_websockets[id].add(invoice_queue)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    finally:
        connected_websockets[id].remove(invoice_queue)


async def updater(copilot_id, data, comment):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        return
    for queue in connected_websockets[copilot_id]:
        await queue.send(f"{data + '-' + comment}")
