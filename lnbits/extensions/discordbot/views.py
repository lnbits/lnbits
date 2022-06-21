from fastapi import Request
from fastapi.params import Depends
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import discordbot_ext, discordbot_renderer


@discordbot_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return discordbot_renderer().TemplateResponse(
        "discordbot/index.html", {"request": request, "user": user.dict()}
    )
