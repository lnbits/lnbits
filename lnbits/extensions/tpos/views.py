from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import tpos_ext
from .crud import get_tpos
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@tpos_ext.get("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("tpos/index.html", {"request":request,"user":g.user})


@tpos_ext.get("/{tpos_id}")
async def tpos(request: Request, tpos_id):
    tpos = await get_tpos(tpos_id)
    if not tpos:
        abort(HTTPStatus.NOT_FOUND, "TPoS does not exist.")

    return await templates.TemplateResponse("tpos/tpos.html", {"request":request,"tpos":tpos})
