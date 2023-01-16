import random
from http import HTTPStatus
from io import BytesIO

import pyqrcode
from fastapi import Depends, Query, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.core.views.api import api_payment
from lnbits.decorators import check_user_exists

from . import satsdice_ext, satsdice_renderer
from .crud import (
    create_satsdice_withdraw,
    get_satsdice_pay,
    get_satsdice_payment,
    get_satsdice_withdraw,
    update_satsdice_payment,
)
from .models import CreateSatsDiceWithdraw

templates = Jinja2Templates(directory="templates")


@satsdice_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return satsdice_renderer().TemplateResponse(
        "satsdice/index.html", {"request": request, "user": user.dict()}
    )


@satsdice_ext.get("/{link_id}", response_class=HTMLResponse)
async def display(request: Request, link_id: str = Query(None)):
    link = await get_satsdice_pay(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="satsdice link does not exist."
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


@satsdice_ext.get(
    "/win/{link_id}/{payment_hash}",
    name="satsdice.displaywin",
    response_class=HTMLResponse,
)
async def displaywin(
    request: Request, link_id: str = Query(None), payment_hash: str = Query(None)
):
    satsdicelink = await get_satsdice_pay(link_id)
    if not satsdicelink:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="satsdice link does not exist."
        )
    withdrawLink = await get_satsdice_withdraw(payment_hash)
    payment = await get_satsdice_payment(payment_hash)
    if not payment or payment.lost:
        return satsdice_renderer().TemplateResponse(
            "satsdice/error.html",
            {"request": request, "link": satsdicelink.id, "paid": False, "lost": True},
        )
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
    status = await api_payment(payment_hash)
    if not rand < chance or not status["paid"]:
        await update_satsdice_payment(payment_hash, lost=1)
        return satsdice_renderer().TemplateResponse(
            "satsdice/error.html",
            {"request": request, "link": satsdicelink.id, "paid": False, "lost": True},
        )
    await update_satsdice_payment(payment_hash, paid=1)
    paylink = await get_satsdice_payment(payment_hash)
    if not paylink:
        return satsdice_renderer().TemplateResponse(
            "satsdice/error.html",
            {"request": request, "link": satsdicelink.id, "paid": False, "lost": True},
        )

    data = CreateSatsDiceWithdraw(
        satsdice_pay=satsdicelink.id,
        value=int(paylink.value * satsdicelink.multiplier),
        payment_hash=payment_hash,
        used=0,
    )

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


@satsdice_ext.get("/img/{link_id}", response_class=HTMLResponse)
async def img(link_id):
    link = await get_satsdice_pay(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="satsdice link does not exist."
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
