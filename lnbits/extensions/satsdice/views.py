from datetime import datetime
from http import HTTPStatus
from lnbits.decorators import check_user_exists, WalletTypeInfo, get_key_type
from . import satsdice_ext, satsdice_renderer
from .crud import (
    get_satsdice_pay,
    update_satsdice_payment,
    get_satsdice_payment,
    create_satsdice_withdraw,
    get_satsdice_withdraw,
)
from lnbits.core.crud import (
    get_payments,
    get_standalone_payment,
    delete_expired_invoices,
    get_balance_checks,
)
from lnbits.core.views.api import api_payment
from lnbits.core.services import check_invoice_status
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User, Payment
from fastapi.params import Depends
from fastapi.param_functions import Query
import random
from .models import CreateSatsDiceWithdraw

templates = Jinja2Templates(directory="templates")


@satsdice_ext.get("/")
async def index(request: Request, user: User = Depends(check_user_exists)):
    return satsdice_renderer().TemplateResponse(
        "satsdice/index.html", {"request": request, "user": user.dict()}
    )


@satsdice_ext.get("/{link_id}")
async def display(request: Request, link_id: str = Query(None)):
    link = await get_satsdice_pay(link_id) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )
    return satsdice_renderer().TemplateResponse(
        "satsdice/display.html",
        {
            "request": request,
            "chance": link.chance,
            "multiplier": link.multiplier,
            "lnurl": link.lnurl(request),
            "unique": True,
        },
    )


@satsdice_ext.get("/win/{link_id}/{payment_hash}", name="satsdice.displaywin")
async def displaywin(
    request: Request, link_id: str = Query(None), payment_hash: str = Query(None)
):
    satsdicelink = await get_satsdice_pay(link_id) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )

    withdrawLink = await get_satsdice_withdraw(payment_hash)
    if withdrawLink:
        return satsdice_renderer().TemplateResponse(
            "satsdice/displaywin.html",
            {
                "request": request,
                "value": withdrawLink.value,
                "chance": satsdicelink.chance,
                "multiplier": satsdicelink.multiplier,
                "lnurl": withdrawLink.lnurl(request),
                "paid": False,
                "lost": False,
            },
        )
    rand = random.randint(0, 100)
    chance = satsdicelink.chance
    print(rand)
    print(chance)
    print(rand < chance)
    status = await api_payment(payment_hash)
    if not rand < chance or not status["paid"]:
        return satsdice_renderer().TemplateResponse(
            "satsdice/error.html",
            {
                "request": request,
                "link": satsdicelink.id,
                "paid": False,
                "lost": True,
            },
        )
    await update_satsdice_payment(payment_hash, paid=1)
    paylink = await get_satsdice_payment(payment_hash)

    data: CreateSatsDiceWithdraw = {
        "satsdice_pay": satsdicelink.id,
        "value": paylink.value * satsdicelink.multiplier,
        "payment_hash": payment_hash,
        "used": 0,
    }

    withdrawLink = await create_satsdice_withdraw(data)
    return satsdice_renderer().TemplateResponse(
        "satsdice/displaywin.html",
        {
            "request": request,
            "value": withdrawLink.value,
            "chance": satsdicelink.chance,
            "multiplier": satsdicelink.multiplier,
            "lnurl": withdrawLink.lnurl(request),
            "paid": False,
            "lost": False,
        },
    )


@satsdice_ext.get("/img/{link_id}")
async def img(link_id):
    link = await get_satsdice_pay(link_id) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )
    qr = pyqrcode.create(link.lnurl)
    stream = BytesIO()
    qr.svg(stream, scale=3)
    return (
        stream.getvalue(),
        200,
        {
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
