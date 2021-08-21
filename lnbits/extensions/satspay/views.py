from quart import g, abort, render_template, jsonify
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import satspay_ext
from .crud import get_charge

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@satspay_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("satspay/index.html", {"request":request, "user":g.user})


@satspay_ext.route("/<charge_id>")
async def display(request: Request, charge_id):
    charge = await get_charge(charge_id) or abort(
        HTTPStatus.NOT_FOUND, "Charge link does not exist."
    )
    return await templates.TemplateResponse("satspay/display.html", {"request":request, "charge":charge})
