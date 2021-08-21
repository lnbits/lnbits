from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from . import example_ext
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@example_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("example/index.html", {"request": request, "user":g.user})
