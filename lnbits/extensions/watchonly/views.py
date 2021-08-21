from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import watchonly_ext
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@watchonly_ext.get("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("watchonly/index.html", {"request":request,"user":g.user})

