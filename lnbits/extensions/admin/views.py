from email.policy import default
from os import getenv

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_admin
from lnbits.requestvars import g
from lnbits.settings import WALLET, settings

from . import admin_ext, admin_renderer

templates = Jinja2Templates(directory="templates")


@admin_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_admin)):
    error, balance = await WALLET.status()

    return admin_renderer().TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "user": user.dict(),
            "settings": settings.dict(),
            "balance": balance,
        },
    )
