from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import swap_ext, swap_renderer

# from .crud import get_domain, purge_addresses

templates = Jinja2Templates(directory="templates")


@swap_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return swap_renderer().TemplateResponse("lnaddress/index.html", {"request": request, "user": user.dict()})

