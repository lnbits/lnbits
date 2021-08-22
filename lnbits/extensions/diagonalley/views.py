from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.diagonalley import diagonalley_ext
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@diagonalley_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("diagonalley/index.html", {"request": request, "user": g.user})