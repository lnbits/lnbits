from quart import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids

from . import captcha_ext
from .crud import get_captcha
from fastapi.templating import Jinja2Templates
from fastapi import Request
templates = Jinja2Templates(directory="templates")

@captcha_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("captcha/index.html", user=g.user)


@captcha_ext.route("/{captcha_id}")
async def display(request: Request, captcha_id):
    captcha = await get_captcha(captcha_id) or abort(
        HTTPStatus.NOT_FOUND, "captcha does not exist."
    )
    return await templates.TemplateResponse("captcha/display.html", {"request": request, "captcha": captcha})
