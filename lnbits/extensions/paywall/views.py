from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import paywall_ext
from .crud import get_paywall


@paywall_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("paywall/index.html", user=g.user)


@paywall_ext.route("/<paywall_id>")
async def display(paywall_id):
    paywall = await get_paywall(paywall_id) or abort(
        HTTPStatus.NOT_FOUND, "Paywall does not exist."
    )
    return await render_template("paywall/display.html", paywall=paywall)
