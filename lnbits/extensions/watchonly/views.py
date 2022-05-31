from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import watchonly_ext, watchonly_renderer

templates = Jinja2Templates(directory="templates")


@watchonly_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return watchonly_renderer().TemplateResponse(
        "watchonly/index.html", {"request": request, "user": user.dict()}
    )
