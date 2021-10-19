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
from lnbits.core.services import check_invoice_status
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User, Payment

from fastapi.params import Depends
from fastapi.param_functions import Query

templates = Jinja2Templates(directory="templates")


@satsdice_ext.get("/")
async def index(request: Request, user: User = Depends(check_user_exists)):
    return satsdice_renderer().TemplateResponse(
        "satsdice/index.html", {"request": request, "user": user.dict()}
    )


@satsdice_ext.get("/{link_id}")
async def display(link_id):
    link = await get_satsdice_pay(link_id) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )
    return satsdice_renderer().TemplateResponse(
        "satsdice/display.html",
        chance=link.chance,
        multiplier=link.multiplier,
        lnurl=link.lnurl,
        unique=True,
    )


@satsdice_ext.get("/win/{link_id}/{payment_hash}")
async def displaywin(link_id: str = Query(None), payment_hash: str = Query(None)):
    satsdicelink = await get_satsdice_pay(link_id) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )
    withdrawLink = await get_satsdice_withdraw(payment_hash)

    if withdrawLink:
        return satsdice_renderer().TemplateResponse(
            "satsdice/displaywin.html",
            value=withdrawLink.value,
            chance=satsdicelink.chance,
            multiplier=satsdicelink.multiplier,
            lnurl=withdrawLink.lnurl,
            paid=False,
            lost=False,
        )

    payment = await get_standalone_payment(payment_hash) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )

    if payment.pending == 1:
        await check_invoice_status(payment.wallet_id, payment_hash)
        payment = await get_standalone_payment(payment_hash) or abort(
            HTTPStatus.NOT_FOUND, "satsdice link does not exist."
        )
        if payment.pending == 1:
            print("pending")
            return satsdice_renderer().TemplateResponse(
                "satsdice/error.html", link=satsdicelink.id, paid=False, lost=False
            )

    await update_satsdice_payment(payment_hash, paid=1)

    paylink = await get_satsdice_payment(payment_hash) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )

    if paylink.lost == 1:
        print("lost")
    return satsdice_renderer().TemplateResponse(
        "satsdice/error.html", link=satsdicelink.id, paid=False, lost=True
    )
    rand = random.randint(0, 100)
    chance = satsdicelink.chance
    if rand > chance:
        await update_satsdice_payment(payment_hash, lost=1)
        return satsdice_renderer().TemplateResponse(
            "satsdice/error.html", link=satsdicelink.id, paid=False, lost=True
        )
    data = []
    data.payment_hash = payment_hash
    data.satsdice_pay = (satsdicelink.id,)
    data.value = (paylink.value * satsdicelink.multiplier,)
    data.used = 0
    withdrawLink = await create_satsdice_withdraw(data)
    return satsdice_renderer().TemplateResponse(
        "satsdice/displaywin.html",
        value=withdrawLink.value,
        chance=satsdicelink.chance,
        multiplier=satsdicelink.multiplier,
        lnurl=withdrawLink.lnurl,
        paid=False,
        lost=False,
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
