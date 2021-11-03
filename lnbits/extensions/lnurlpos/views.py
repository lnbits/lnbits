from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists

from .crud import get_lnurlpos, get_lnurlpospayment
from functools import wraps
from lnbits.core.crud import get_standalone_payment
import hashlib
from lnbits.core.services import check_invoice_status
from lnbits.core.crud import update_payment_status
from lnbits.core.views.api import api_payment
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from fastapi.params import Depends
from fastapi.param_functions import Query
import random

from datetime import datetime
from http import HTTPStatus
from . import lnurlpos_ext, lnurlpos_renderer
from lnbits.core.models import User, Payment

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
        "lnurlpos/error.html",
        {"request": request, "pin": "filler", "not_paid": True},
    )
