from typing import List

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse  # type: ignore

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import copilot_ext, copilot_renderer

templates = Jinja2Templates(directory="templates")


@copilot_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return copilot_renderer().TemplateResponse(
        "copilot/index.html", {"request": request, "user": user.dict()}
    )


@copilot_ext.get("/cp/", response_class=HTMLResponse)
async def compose(request: Request):
    return copilot_renderer().TemplateResponse(
        "copilot/compose.html", {"request": request}
    )


@copilot_ext.get("/pn/", response_class=HTMLResponse)
async def panel(request: Request):
    return copilot_renderer().TemplateResponse(
        "copilot/panel.html", {"request": request}
    )
