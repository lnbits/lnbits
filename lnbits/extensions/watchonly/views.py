from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import watchonly_ext


@watchonly_ext.get("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("watchonly/index.html", user=g.user)

