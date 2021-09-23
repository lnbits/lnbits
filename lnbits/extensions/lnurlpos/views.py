from quart import g, abort, render_template, jsonify, websocket
from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists, validate_uuids
from . import lnurlpos_ext
from .crud import get_lnurlpos
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


@lnurlpos_ext.route("/<payment_hash>/<nonce>")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def displaypin(payment_hash, nonce):
    lnurlpos = await get_lnurlpos(pos_id)
    payment = await get_standalone_payment(payment_hash) or abort(
        HTTPStatus.NOT_FOUND, "Payment does not exist."
    )
    if payment.pending == 1:
        return await render_template("lnurlpos/error.html", pin="filler", not_paid=True)
    if "lnurlpos" != payment.extra.get("tag"):
        HTTPStatus.NOT_FOUND, "Not LNURLPoS."
    lnurlpos = payment.extra.get("lnurlpos")
    payload = payment.extra.get("payload")
    pos = await get_lnurlpos(lnurlpos)
    if not pos:
        return jsonify({"status": "ERROR", "reason": "lnurlpos not found."})
    nonce1 = bytes.fromhex(nonce)
    payload1 = bytes.fromhex(payload)
    h = hashlib.sha256(nonce1)
    h.update(pos.key.encode())
    s = h.digest()
    res = bytearray(payload1)
    for i in range(len(res)):
        res[i] = res[i] ^ s[i]
    decryptedKey = int.from_bytes(res[:2], "little")

    return await render_template("lnurlpos/paid.html", pin=decryptedKey, not_paid=True)
