from quart import g, abort, render_template
from http import HTTPStatus
import pyqrcode
from io import BytesIO
from lnbits.decorators import check_user_exists, validate_uuids

from . import lnurlflip_ext
from .crud import get_lnurlflip_link, chunks


@lnurlflip_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnurlflip/index.html", user=g.user)


@lnurlflip_ext.route("/<link_id>")
async def display(link_id):
    link = await get_lnurlflip_link(link_id, 0) or abort(
        HTTPStatus.NOT_FOUND, "lnurlflip link does not exist."
    )
    return await render_template("lnurlflip/display.html", link=link, unique=True)


@lnurlflip_ext.route("/img/<link_id>")
async def img(link_id):
    link = await get_lnurlflip_link(link_id, 0) or abort(
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


@lnurlflip_ext.route("/print/<link_id>")
async def print_qr(link_id):
    link = await get_lnurlflip_link(link_id) or abort(
        HTTPStatus.NOT_FOUND, "lnurlflip link does not exist."
    )
    if link.uses == 0:
        return await render_template("lnurlflip/print_qr.html", link=link, unique=False)
    links = []
    count = 0
    for x in link.usescsv.split(","):
        linkk = await get_lnurlflip_link(link_id, count) or abort(
            HTTPStatus.NOT_FOUND, "lnurlflip link does not exist."
        )
        links.append(str(linkk.lnurl))
        count = count + 1
    page_link = list(chunks(links, 2))
    linked = list(chunks(page_link, 5))
    return await render_template("lnurlflip/print_qr.html", link=linked, unique=True)
