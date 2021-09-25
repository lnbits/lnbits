from quart import g, abort, render_template
from http import HTTPStatus
import pyqrcode
from io import BytesIO
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.core.crud import get_user, get_standalone_payment
from lnbits.core.services import check_invoice_status
import random

from . import satsdice_ext
from .crud import (
    get_satsdice_pay,
    update_satsdice_payment,
    get_satsdice_payment,
    create_satsdice_withdraw,
    get_satsdice_withdraw,
)


@satsdice_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("satsdice/index.html", user=g.user)


@satsdice_ext.route("/<link_id>")
async def display(link_id):
    link = await get_satsdice_pay(link_id) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )
    return await render_template(
        "satsdice/display.html",
        chance=link.chance,
        multiplier=link.multiplier,
        lnurl=link.lnurl,
        unique=True,
    )


@satsdice_ext.route("/win/<link_id>/<payment_hash>")
async def displaywin(link_id, payment_hash):
    satsdicelink = await get_satsdice_pay(link_id) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )
    withdrawLink = await get_satsdice_withdraw(payment_hash)

    if withdrawLink:
        return await render_template(
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
            return await render_template(
                "satsdice/error.html", link=satsdicelink.id, paid=False, lost=False
            )

    await update_satsdice_payment(payment_hash, paid=1)

    paylink = await get_satsdice_payment(payment_hash) or abort(
        HTTPStatus.NOT_FOUND, "satsdice link does not exist."
    )

    if paylink.lost == 1:
        print("lost")
        return await render_template(
            "satsdice/error.html", link=satsdicelink.id, paid=False, lost=True
        )
    rand = random.randint(0, 100)
    chance = satsdicelink.chance
    if rand > chance:
        await update_satsdice_payment(payment_hash, lost=1)
        return await render_template(
            "satsdice/error.html", link=satsdicelink.id, paid=False, lost=True
        )

    withdrawLink = await create_satsdice_withdraw(
        payment_hash=payment_hash,
        satsdice_pay=satsdicelink.id,
        value=paylink.value * satsdicelink.multiplier,
        used=0,
    )

    return await render_template(
        "satsdice/displaywin.html",
        value=withdrawLink.value,
        chance=satsdicelink.chance,
        multiplier=satsdicelink.multiplier,
        lnurl=withdrawLink.lnurl,
        paid=False,
        lost=False,
    )


@satsdice_ext.route("/img/<link_id>")
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
