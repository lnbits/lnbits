from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import nostrrelay_ext, nostrrelay_renderer

templates = Jinja2Templates(directory="templates")


@nostrrelay_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return nostrrelay_renderer().TemplateResponse(
        "nostrrelay/index.html", {"request": request, "user": user.dict()}
    )


@nostrrelay_ext.get("/public")
async def nostrrelay(request: Request, nostrrelay_id):
    return nostrrelay_renderer().TemplateResponse(
        "nostrrelay/public.html",
        {
            "request": request,
            # "nostrrelay": relay,
            "web_manifest": f"/nostrrelay/manifest/{nostrrelay_id}.webmanifest",
        },
    )
