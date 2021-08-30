from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids

from . import lnaddress_ext


@lnaddress_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("example/index.html", user=g.user)
