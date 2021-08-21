from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

from . import streamalerts_ext
from .crud import get_service
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@streamalerts_ext.get("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    """Return the extension's settings page"""
    return await templates.TemplateResponse("streamalerts/index.html", {"request":request, "user":g.user})


@streamalerts_ext.get("/<state>")
async def donation(request: Request, state):
    """Return the donation form for the Service corresponding to state"""
    service = await get_service(0, by_state=state)
    if not service:
        abort(HTTPStatus.NOT_FOUND, "Service does not exist.")
    return await templates.TemplateResponse(
        "streamalerts/display.html",
        {"request":request, 
        "twitchuser":service.twitchuser,
        "service":service.id}
    )
