from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import amilk_ext
from .crud import get_amilk


@amilk_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("amilk/index.html", user=g.user)


@amilk_ext.route("/<amilk_id>")
async def wall(amilk_id):
    amilk = await get_amilk(amilk_id)
    if not amilk:
        abort(HTTPStatus.NOT_FOUND, "AMilk does not exist.")

    return await render_template("amilk/wall.html", amilk=amilk)
