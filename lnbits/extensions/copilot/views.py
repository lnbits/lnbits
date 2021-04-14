from quart import g, abort, render_template, jsonify, websocket
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import copilot_ext
from .crud import get_copilot

@copilot_ext.websocket('/ws')
async def ws():
    while True:
        data = await websocket.receive()
        await websocket.send(f"echo {data}")
        
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