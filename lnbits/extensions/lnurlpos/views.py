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
from lnbits.core.services import check_invoice_status
from lnbits.core.crud import update_payment_status


@lnurlpos_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnurlpos/index.html", user=g.user)


@lnurlpos_ext.route("/<paymentid>")
async def displaypin(paymentid):
    lnurlpospayment = await get_lnurlpospayment(paymentid)
    if not lnurlpospayment:
        return jsonify({"status": "ERROR", "reason": "lmurlpos payment"})
    pos = await get_lnurlpos(lnurlpospayment.posid)
    if not pos:
        return jsonify({"status": "ERROR", "reason": "lnurlpos not found."})
    status = await check_invoice_status(pos.wallet, lnurlpospayment.payhash)

    is_paid = not status.pending
    if not is_paid:
        return await render_template("lnurlpos/error.html", pin="filler", not_paid=True)
    await update_payment_status(checking_id=lnurlpospayment.payhash, pending=True)
    return await render_template(
        "lnurlpos/paid.html", pin=lnurlpospayment.pin, not_paid=True
    )
