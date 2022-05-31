from quart import g, abort, render_template, jsonify, websocket
from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists, validate_uuids
from . import copilot_ext
from .crud import get_copilot
from quart import g, abort, render_template, jsonify, websocket
from functools import wraps
import trio
import shortuuid
from . import copilot_ext


@copilot_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("copilot/index.html", user=g.user)


@copilot_ext.route("/cp/")
async def compose():
    return await render_template("copilot/compose.html")


@copilot_ext.route("/pn/")
async def panel():
    return await render_template("copilot/panel.html")


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
