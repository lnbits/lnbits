from quart import g, abort, render_template
from http import HTTPStatus
import pyqrcode
from io import BytesIO
from lnbits.decorators import check_user_exists, validate_uuids

from . import lnurlflip_ext
from .crud import get_lnurlflip_pay


@lnurlflip_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnurlflip/index.html", user=g.user)


@lnurlflip_ext.route("/<link_id>")
async def display(link_id):
    link = await get_lnurlflip_pay(link_id, 0) or abort(
        HTTPStatus.NOT_FOUND, "lnurlflip link does not exist."
    )
    return await render_template("lnurlflip/display.html", link=link, unique=True)


@lnurlflip_ext.route("/img/<link_id>")
async def img(link_id):
    link = await get_lnurlflip_pay(link_id, 0) or abort(
        HTTPStatus.NOT_FOUND, "lnurlflip link does not exist."
    )
    qr = pyqrcode.create(link.lnurl)
    stream = BytesIO()
    qr.svg(stream, scale=3)
    return (
        stream.getvalue(),
        200,
        {
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
