from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import deezy_ext, deezy_renderer

templates = Jinja2Templates(directory="templates")


@deezy_ext.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: User = Depends(check_user_exists),  # type: ignore
):
    return deezy_renderer().TemplateResponse(
        "deezy/index.html", {"request": request, "user": user.dict()}
    )
