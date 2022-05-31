from fastapi.param_functions import Depends
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import hivemind_ext, hivemind_renderer


@hivemind_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return hivemind_renderer().TemplateResponse(
        "hivemind/index.html", {"request": request, "user": user.dict()}
    )
