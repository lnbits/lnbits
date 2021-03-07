import time
from quart import g, render_template, request
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.core.models import Payment
from lnbits.core.crud import get_standalone_payment

from . import offlineshop_ext
from .crud import get_item, get_shop


@offlineshop_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("offlineshop/index.html", user=g.user)


@offlineshop_ext.route("/confirmation")
async def confirmation_code():
    payment_hash = request.args.get("p")
    payment: Payment = await get_standalone_payment(payment_hash)
    if not payment:
        return f"Couldn't find the payment {payment_hash}.", HTTPStatus.NOT_FOUND
    if payment.pending:
        return f"Payment {payment_hash} wasn't received yet. Please try again in a minute.", HTTPStatus.PAYMENT_REQUIRED

    if payment.time + 60 * 15 < time.time():
        return "too much time has passed."

    item = await get_item(payment.extra.get("item"))
    shop = await get_shop(item.shop)
    return shop.next_word(payment_hash)
