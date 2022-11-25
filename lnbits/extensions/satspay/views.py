from http import HTTPStatus

from fastapi import Response
from fastapi.param_functions import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits.core.crud import get_wallet
from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import LNBITS_ADMIN_USERS

from . import satspay_ext, satspay_renderer
from .crud import get_charge, get_charge_config, get_themes, get_theme

templates = Jinja2Templates(directory="templates")

@satspay_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    admin = False
    if LNBITS_ADMIN_USERS and user.id not in LNBITS_ADMIN_USERS:
        admin = True
    return satspay_renderer().TemplateResponse(
        "satspay/index.html", {"request": request, "user": user.dict(), "admin": admin}
    )


@satspay_ext.get("/{charge_id}", response_class=HTMLResponse)
async def display(request: Request, charge_id: str):
    charge = await get_charge(charge_id)
    if not charge:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Charge link does not exist."
        )
    wallet = await get_wallet(charge.lnbitswallet)
    onchainwallet_config = await get_charge_config(charge_id)
    inkey = wallet.inkey if wallet else None
    mempool_endpoint = (
        onchainwallet_config.mempool_endpoint if onchainwallet_config else None
    )
    return satspay_renderer().TemplateResponse(
        "satspay/display.html",
        {
            "request": request,
            "charge_data": charge.dict(),
            "wallet_inkey": inkey,
            "mempool_endpoint": mempool_endpoint,
        },
    )


@satspay_ext.get("/css/{css_id}")
async def display(css_id: str, response: Response):
    theme = await get_theme(css_id)
    if theme:
        return Response(content=theme.custom_css, media_type="text/css")

    return None
