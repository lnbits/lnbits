import os

from fastapi import Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from fastapi.params import Depends

from starlette.responses import HTMLResponse
from starlette.responses import FileResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import pushnotifications_ext, pushnotifications_renderer
from .tasks import get_vapid_public_key

templates = Jinja2Templates(directory="templates")


@pushnotifications_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return pushnotifications_renderer().TemplateResponse(
        "pushnotifications/index.html",
        {
            "request": request,
            "user": user.dict(),
            "vapid_public_key": get_vapid_public_key()
        }
    )


@pushnotifications_ext.get("/service_worker.js", response_class=FileResponse)
async def service_worker(request: Request):
    return FileResponse(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "service_worker.js"
        )
    )
