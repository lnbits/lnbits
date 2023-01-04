from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import example_ext, example_renderer

templates = Jinja2Templates(directory="templates")


@example_ext.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: User = Depends(check_user_exists),
):
    return example_renderer().TemplateResponse(
        "example/index.html", {"request": request, "user": user.dict()}
    )
