from quart import g, abort, render_template, jsonify, websocket
from http import HTTPStatus
import httpx

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

socket_relay = {}


@copilot_ext.websocket("/ws/panel/<copilot_id>")
async def ws_panel(copilot_id):
    global socket_relay
    while True:
        data = await websocket.receive()
        socket_relay[copilot_id] = shortuuid.uuid()[:5] + "-" + data + "-" + "none"


@copilot_ext.websocket("/ws/compose/<copilot_id>")
async def ws_compose(copilot_id):
    global socket_relay
    while True:
        data = await websocket.receive()
        await websocket.send(socket_relay[copilot_id])


async def updater(data, comment, copilot):
    global socket_relay
    socket_relay[copilot] = shortuuid.uuid()[:5] + "-" + str(data) + "-" + str(comment)




##################WEBSOCKET ROUTES########################

# socket_relay is a list where the control panel or
# lnurl endpoints can leave a message for the compose window

connected_websockets = set()


def collect_websocket(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        global connected_websockets
        send_channel, receive_channel = trio.open_memory_channel(0)
        connected_websockets.add(send_channel)
        try:
            return await func(receive_channel, *args, **kwargs)
        finally:
            connected_websockets.remove(send_channel)

    return wrapper


@copilot_ext.websocket("/ws")
@collect_websocket
async def wss(receive_channel):

    while True:
        data = await receive_channel.receive()
        await websocket.send(data)