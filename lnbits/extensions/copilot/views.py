from quart import g, abort, render_template, jsonify, websocket
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import copilot_ext
from .crud import get_copilot

from quart import g, abort, render_template, jsonify, websocket
from functools import wraps
import trio 
import shortuuid
from . import copilot_ext

connected_websockets = {}

@copilot_ext.websocket('/ws/panel/<copilot_id>')
async def ws_panel(copilot_id):
    global connected_websockets
    while True:
        data = await websocket.receive()
        connected_websockets[copilot_id] = shortuuid.uuid() + '-' + data

@copilot_ext.websocket('/ws/compose/<copilot_id>')
async def ws_compose(copilot_id):
    global connected_websockets
    while True:
        data = await websocket.receive()
        await websocket.send(connected_websockets[copilot_id])
        
@copilot_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("copilot/index.html", user=g.user)


@copilot_ext.route("/cp/<copilot_id>")
async def compose(copilot_id):
    copilot = await get_copilot(copilot_id) or abort(
        HTTPStatus.NOT_FOUND, "Copilot link does not exist."
    )
    return await render_template("copilot/compose.html", copilot=copilot)

@copilot_ext.route("/<copilot_id>")
async def panel(copilot_id):
    copilot = await get_copilot(copilot_id) or abort(
        HTTPStatus.NOT_FOUND, "Copilot link does not exist."
    )
    return await render_template("copilot/panel.html", copilot=copilot)