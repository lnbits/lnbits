from http import HTTPStatus

from fastapi.param_functions import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import strike_ext, strike_renderer
from .crud import get_configuration

templates = Jinja2Templates(directory="templates")


@strike_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return strike_renderer().TemplateResponse(
        "strike/index.html", {"request": request, "user": user.dict()}
    )


@strike_ext.get("/{id}", response_class=HTMLResponse)
async def display(request: Request, id):
    config = await get_configuration(id)
    if not config:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Configuration link does not exist."
        )
    wallet = await get_wallet(config.lnbits_wallet)
    return strike_renderer().TemplateResponse(
        "strike/display.html",
        {"request": request, "config": config, "wallet_key": wallet.inkey},
    )
