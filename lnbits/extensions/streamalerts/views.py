from http import HTTPStatus

from fastapi import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import streamalerts_ext, streamalerts_renderer
from .crud import get_service

templates = Jinja2Templates(directory="templates")


@streamalerts_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    """Return the extension's settings page"""
    return streamalerts_renderer().TemplateResponse(
        "streamalerts/index.html", {"request": request, "user": user.dict()}
    )


@streamalerts_ext.get("/{state}")
async def donation(state, request: Request):
    """Return the donation form for the Service corresponding to state"""
    service = await get_service(0, by_state=state)
    if not service:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Service does not exist."
        )
    return streamalerts_renderer().TemplateResponse(
        "streamalerts/display.html",
        {"request": request, "twitchuser": service.twitchuser, "service": service.id},
    )
