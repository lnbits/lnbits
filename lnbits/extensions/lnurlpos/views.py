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

from . import lnurlpos_ext, lnurlpos_renderer
from .crud import get_lnurlpos, get_lnurlpospayment

templates = Jinja2Templates(directory="templates")


@lnurlpos_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnurlpos_renderer().TemplateResponse(
        "lnurlpos/index.html", {"request": request, "user": user.dict()}
    )


@lnurlpos_ext.get(
    "/{paymentid}", name="lnurlpos.displaypin", response_class=HTMLResponse
)
async def displaypin(request: Request, paymentid: str = Query(None)):
    lnurlpospayment = await get_lnurlpospayment(paymentid)
    if not lnurlpospayment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No lmurlpos payment"
        )
    pos = await get_lnurlpos(lnurlpospayment.posid)
    if not pos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurlpos not found."
        )
    status = await api_payment(lnurlpospayment.payhash)
    if status["paid"]:
        await update_payment_status(checking_id=lnurlpospayment.payhash, pending=True)
        return lnurlpos_renderer().TemplateResponse(
            "lnurlpos/paid.html", {"request": request, "pin": lnurlpospayment.pin}
        )
    return lnurlpos_renderer().TemplateResponse(
        "lnurlpos/error.html", {"request": request, "pin": "filler", "not_paid": True}
    )
