from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists, validate_uuids

from .crud import get_copilot

from functools import wraps

from lnbits.decorators import check_user_exists

from . import copilot_ext, copilot_renderer
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates

from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User

templates = Jinja2Templates(directory="templates")


@copilot_ext.route("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return copilot_renderer().TemplateResponse(
        "copilot/index.html", {"request": request, "user": user.dict()}
    )


@copilot_ext.route("/cp/", response_class=HTMLResponse)
async def compose(request: Request):
    return copilot_renderer().TemplateResponse(
        "copilot/compose.html", {"request": request}
    )


@copilot_ext.route("/pn/", response_class=HTMLResponse)
async def panel(request: Request):
    return copilot_renderer().TemplateResponse(
        "copilot/panel.html", {"request": request}
    )


##################WEBSOCKET ROUTES########################

# socket_relay is a list where the control panel or
# lnurl endpoints can leave a message for the compose window

connected_websockets = defaultdict(set)


@copilot_ext.websocket("/ws/<id>/")
async def wss(id):
    copilot = await get_copilot(id)
    if not copilot:
        return "", HTTPStatus.FORBIDDEN
    global connected_websockets
    send_channel, receive_channel = trio.open_memory_channel(0)
    connected_websockets[id].add(send_channel)
    try:
        while True:
            data = await receive_channel.receive()
            await websocket.send(data)
    finally:
        connected_websockets[id].remove(send_channel)


async def updater(copilot_id, data, comment):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        return
    for queue in connected_websockets[copilot_id]:
        await queue.send(f"{data + '-' + comment}")
