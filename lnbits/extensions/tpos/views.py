from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from lnbits.extensions.tpos import tpos_ext
from .crud import get_tpos


@tpos_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("tpos/index.html", user=g.user)


@tpos_ext.route("/<tpos_id>")
async def tpos(tpos_id):
    tpos = get_tpos(tpos_id) or abort(HTTPStatus.NOT_FOUND, "TPoS does not exist.")

    return await render_template("tpos/tpos.html", tpos=tpos)
