from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.crud import update_payment_status
from lnbits.core.models import User
from lnbits.core.views.api import api_payment
from lnbits.decorators import check_user_exists

from . import lnurldevice_ext, lnurldevice_renderer
from .crud import get_lnurldevice, get_lnurldevicepayment

templates = Jinja2Templates(directory="templates")


@lnurldevice_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnurldevice_renderer().TemplateResponse(
        "lnurldevice/index.html", {"request": request, "user": user.dict()}
    )


@lnurldevice_ext.get(
    "/{paymentid}", name="lnurldevice.displaypin", response_class=HTMLResponse
)
async def displaypin(request: Request, paymentid: str = Query(None)):
    lnurldevicepayment = await get_lnurldevicepayment(paymentid)
    if not lnurldevicepayment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No lmurldevice payment"
        )
    device = await get_lnurldevice(lnurldevicepayment.deviceid)
    if not device:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurldevice not found."
        )
    status = await api_payment(lnurldevicepayment.payhash)
    if status["paid"]:
        await update_payment_status(
            checking_id=lnurldevicepayment.payhash, pending=True
        )
        return lnurldevice_renderer().TemplateResponse(
            "lnurldevice/paid.html", {"request": request, "pin": lnurldevicepayment.pin}
        )
    return lnurldevice_renderer().TemplateResponse(
        "lnurldevice/error.html",
        {"request": request, "pin": "filler", "not_paid": True},
    )
