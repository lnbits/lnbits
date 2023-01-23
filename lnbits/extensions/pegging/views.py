from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import settings

from . import pegging_ext, pegging_renderer
from .crud import get_pegging

templates = Jinja2Templates(directory="templates")


@pegging_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return pegging_renderer().TemplateResponse(
        "pegging/index.html", {"request": request, "user": user.dict()}
    )
