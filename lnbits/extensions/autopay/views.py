from quart import render_template, g
from lnbits.decorators import check_user_exists, validate_uuids

from . import autopay_ext


@autopay_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("autopay/index.html", user=g.user)
