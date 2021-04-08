from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import watchonly_ext


@watchonly_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("watchonly/index.html", user=g.user)


@watchonly_ext.route("/<charge_id>")
async def display(charge_id):
    link = get_payment(charge_id) or abort(
        HTTPStatus.NOT_FOUND, "Charge link does not exist."
    )

    return await render_template("watchonly/display.html", link=link)
