from quart import g, abort, render_template, jsonify
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import satspay_ext
from .crud import get_charge


@satspay_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("satspay/index.html", user=g.user)


@satspay_ext.route("/<charge_id>")
async def display(charge_id):
    charge = await get_charge(charge_id) or abort(
        HTTPStatus.NOT_FOUND, "Charge link does not exist."
    )
    return await render_template("satspay/display.html", charge=charge)
