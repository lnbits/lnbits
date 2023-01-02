from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import scrub_ext, scrub_renderer

templates = Jinja2Templates(directory="templates")


@scrub_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return scrub_renderer().TemplateResponse(
        "scrub/index.html", {"request": request, "user": user.dict()}
    )
