from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

from . import tipjar_ext
from .crud import get_tipjar


@tipjar_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    """Return the extension's settings page"""
    return await render_template("tipjar/index.html", user=g.user)


@tipjar_ext.route("/<id>")
async def tip(id):
    """Return the donation form for the Tipjar corresponding to id"""
    tipjar = await get_tipjar(id)
    if not tipjar:
        abort(HTTPStatus.NOT_FOUND, "TipJar does not exist.")
    return await render_template(
        "tipjar/display.html",
        donatee=tipjar.name,
        tipjar=tipjar.id
    )
