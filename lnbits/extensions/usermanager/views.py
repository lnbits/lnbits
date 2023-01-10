from fastapi import Depends, Request
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import usermanager_ext, usermanager_renderer


@usermanager_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return usermanager_renderer().TemplateResponse(
        "usermanager/index.html", {"request": request, "user": user.dict()}
    )
