from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids

from . import jitsi_ext


@jitsi_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("jitsi/index.html", user=g.user)
