from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import paywall_ext
from .crud import get_paywall
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@paywall_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("paywall/index.html", {"request": request,"user":g.user})


@paywall_ext.route("/<paywall_id>")
async def display(request: Request, paywall_id):
    paywall = await get_paywall(paywall_id) or abort(
        HTTPStatus.NOT_FOUND, "Paywall does not exist."
    )
    return await templates.TemplateResponse("paywall/display.html", {"request": request,"paywall":paywall})
