from email.policy import default
from os import getenv

from fastapi import Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.extensions.admin import admin_ext
from lnbits.requestvars import g

from . import admin_ext, admin_renderer
from .crud import get_admin, get_funding

templates = Jinja2Templates(directory="templates")

@admin_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    admin = await get_admin()
    funding = [f.dict() for f in await get_funding()]
    error, balance = await g().WALLET.status()
    
    return admin_renderer().TemplateResponse(
        "admin/index.html", {
            "request": request,
            "user": user.dict(),
            "admin": admin.dict(),
            "funding": funding,
            "settings": g().admin_conf.dict(),
            "balance": balance
        }
    )
