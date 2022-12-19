from http import HTTPStatus

from fastapi import Response
from fastapi.param_functions import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.extensions.satspay.helpers import public_charge

from . import satspay_ext, satspay_renderer
from .crud import get_charge, get_theme

templates = Jinja2Templates(directory="templates")


@satspay_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return satspay_renderer().TemplateResponse(
        "satspay/index.html",
        {"request": request, "user": user.dict(), "admin": user.admin},
    )


@satspay_ext.get("/{charge_id}", response_class=HTMLResponse)
async def display_charge(request: Request, charge_id: str):
    charge = await get_charge(charge_id)
    if not charge:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Charge link does not exist."
        )

    return satspay_renderer().TemplateResponse(
        "satspay/display.html",
        {
            "request": request,
            "charge_data": public_charge(charge),
            "mempool_endpoint": charge.config.mempool_endpoint,
            "network": charge.config.network,
        },
    )


@satspay_ext.get("/css/{css_id}")
async def display_css(css_id: str):
    theme = await get_theme(css_id)
    if theme:
        return Response(content=theme.custom_css, media_type="text/css")
    return None
