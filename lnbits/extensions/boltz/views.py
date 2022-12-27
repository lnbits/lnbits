from urllib.parse import urlparse

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import boltz_ext, boltz_renderer

templates = Jinja2Templates(directory="templates")


@boltz_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    root_url = urlparse(str(request.url)).netloc
    return boltz_renderer().TemplateResponse(
        "boltz/index.html",
        {"request": request, "user": user.dict(), "root_url": root_url},
    )
