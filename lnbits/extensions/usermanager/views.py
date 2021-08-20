from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids

from . import usermanager_ext


@usermanager_ext.get("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("usermanager/index.html", user=g.user)
