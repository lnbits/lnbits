from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import lnurlp_ext
from .crud import get_pay_link
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@lnurlp_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("lnurlp/index.html", {"request": request, "user":g.user})


@lnurlp_ext.route("/<link_id>")
async def display(request: Request,link_id):
    link = await get_pay_link(link_id)
    if not link:
        abort(HTTPStatus.NOT_FOUND, "Pay link does not exist.")

    return await templates.TemplateResponse("lnurlp/display.html", {"request": request, "link":link})


@lnurlp_ext.route("/print/<link_id>")
async def print_qr(request: Request,link_id):
    link = await get_pay_link(link_id)
    if not link:
        abort(HTTPStatus.NOT_FOUND, "Pay link does not exist.")

    return await templates.TemplateResponse("lnurlp/print_qr.html", {"request": request, "link":link})
