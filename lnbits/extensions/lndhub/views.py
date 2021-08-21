from quart import render_template, g

from lnbits.decorators import check_user_exists, validate_uuids
from . import lndhub_ext
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@lndhub_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def lndhub_index(request: Request):
    return await templates.TemplateResponse("lndhub/index.html", {"request": request,"user":g.user})
