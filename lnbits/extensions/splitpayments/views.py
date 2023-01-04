from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import splitpayments_ext, splitpayments_renderer

templates = Jinja2Templates(directory="templates")


@splitpayments_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return splitpayments_renderer().TemplateResponse(
        "splitpayments/index.html", {"request": request, "user": user.dict()}
    )
