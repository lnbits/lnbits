import time
from datetime import datetime
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


@offlineshop_ext.route("/print")
async def print_qr_codes():
    items = []
    for item_id in request.args.get("items").split(","):
        item = await get_item(item_id)
        if item:
            items.append(
                {
                    "lnurl": item.lnurl,
                    "name": item.name,
                    "price": f"{item.price} {item.unit}",
                }
            )

    return await render_template("offlineshop/print.html", items=items)


@offlineshop_ext.route("/confirmation")
async def confirmation_code():
    style = "<style>* { font-size: 100px}</style>"

    payment_hash = request.args.get("p")
    payment: Payment = await get_standalone_payment(payment_hash)
    if not payment:
        return (
            f"Couldn't find the payment {payment_hash}." + style,
            HTTPStatus.NOT_FOUND,
        )
    if payment.pending:
        return (
            f"Payment {payment_hash} wasn't received yet. Please try again in a minute."
            + style,
            HTTPStatus.PAYMENT_REQUIRED,
        )

    if payment.time + 60 * 15 < time.time():
        return "too much time has passed." + style

    item = await get_item(payment.extra.get("item"))
    shop = await get_shop(item.shop)

    return (
        f"""
[{shop.get_code(payment_hash)}]<br>
{item.name}<br>
{item.price} {item.unit}<br>
{datetime.utcfromtimestamp(payment.time).strftime('%Y-%m-%d %H:%M:%S')}
    """
        + style
    )
