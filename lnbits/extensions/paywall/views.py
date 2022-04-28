from http import HTTPStatus

from fastapi import Depends
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import paywall_ext, paywall_renderer
from .crud import get_paywall


@paywall_ext.get("/")
async def index(request: Request, user: User = Depends(check_user_exists)):
    return paywall_renderer().TemplateResponse(
        "paywall/index.html", {"request": request, "user": user.dict()}
    )


@paywall_ext.get("/{paywall_id}")
async def display(request: Request, paywall_id):
    paywall = await get_paywall(paywall_id)
    if not paywall:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Paywall does not exist."
        )
    return paywall_renderer().TemplateResponse(
        "paywall/display.html", {"request": request, "paywall": paywall}
    )
