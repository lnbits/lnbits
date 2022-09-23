from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import LNBITS_CUSTOM_LOGO, LNBITS_SITE_TITLE

from . import gerty_ext, gerty_renderer
from .crud import get_gerty

templates = Jinja2Templates(directory="templates")

@gerty_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return gerty_renderer().TemplateResponse(
        "gerty/index.html", {"request": request, "user": user.dict()}
    )

