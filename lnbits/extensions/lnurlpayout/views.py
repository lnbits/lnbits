from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import lnurlpayout_ext, lnurlpayout_renderer
from .crud import get_lnurlpayout

templates = Jinja2Templates(directory="templates")


@lnurlpayout_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnurlpayout_renderer().TemplateResponse(
        "lnurlpayout/index.html", {"request": request, "user": user.dict()}
    )
