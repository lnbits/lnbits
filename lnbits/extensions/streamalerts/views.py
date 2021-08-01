from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

from . import streamalerts_ext
from .crud import get_service


@streamalerts_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    """Return the extension's settings page"""
    return await render_template("streamalerts/index.html", user=g.user)


@streamalerts_ext.route("/<state>")
async def donation(state):
    """Return the donation form for the Service corresponding to state"""
    service = await get_service(0, by_state=state)
    if not service:
        abort(HTTPStatus.NOT_FOUND, "Service does not exist.")
    return await render_template(
        "streamalerts/display.html",
        twitchuser=service.twitchuser,
        service=service.id
    )
