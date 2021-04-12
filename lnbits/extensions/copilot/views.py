from quart import g, abort, render_template, jsonify
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import copilot_ext
from .crud import get_copilot


@copilot_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("copilot/index.html", user=g.user)


@copilot_ext.route("/<copilot_id>")
async def display(copilot_id):
    copilot = await get_copilot(copilot_id) or abort(
        HTTPStatus.NOT_FOUND, "Charge link does not exist."
    )
    return await render_template("copilot/display.html", copilot=copilot)
