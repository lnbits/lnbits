from quart import g, abort, render_template, jsonify, websocket
from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists, validate_uuids
from . import lnurlpos_ext
from .crud import get_lnurlpos, get_lnurlpospayment
from quart import g, abort, render_template, jsonify, websocket
from functools import wraps
import trio
import shortuuid
from . import lnurlpos_ext
from lnbits.core.crud import get_standalone_payment
import hashlib


@lnurlpos_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnurlpos/index.html", user=g.user)


@lnurlpos_ext.route("/<paymentid>")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def displaypin(paymentid):
    lnurlpospayment = await get_lnurlpospayment(paymentid)
    pos = await get_lnurlpos(lnurlpospayment.posid)
    if not pos:
        return jsonify({"status": "ERROR", "reason": "lnurlpos not found."})

    payment = await get_standalone_payment(payment_hash) or abort(
        HTTPStatus.NOT_FOUND, "Payment does not exist."
    )
    if payment.pending == 1:
        return await render_template("lnurlpos/error.html", pin="filler", not_paid=True)
    if "lnurlpos" != payment.extra.get("tag"):
        HTTPStatus.NOT_FOUND, "Not LNURLPoS."

    return await render_template(
        "lnurlpos/paid.html", pin=lnurlpospayment.pin, not_paid=True
    )
