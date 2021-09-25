import json
import hashlib
import math
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore
from lnurl.types import LnurlPayMetadata
from lnbits.core.services import create_invoice
from hashlib import md5

from . import lnurlpos_ext
from .crud import (
    get_lnurlpos,
    create_lnurlpospayment,
    get_lnurlpospayment,
    update_lnurlpospayment,
)
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis


@lnurlpos_ext.route("/api/v1/lnurl/<nonce>/<payload>/<pos_id>", methods=["GET"])
async def lnurl_response(nonce, pos_id, payload):
    pos = await get_lnurlpos(pos_id)
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
        decryptedAmount = float(int.from_bytes(res[2:6], "little") / 100)
        decryptedPin = int.from_bytes(res[:2], "little")
    if type(decryptedAmount) != float:
        return jsonify({"status": "ERROR", "reason": "Not an amount."})
    price_msat = (
        await fiat_amount_as_satoshis(decryptedAmount, pos.currency)
        if pos.currency != "sat"
        else pos.currency
    ) * 1000

    lnurlpospayment = await create_lnurlpospayment(
        posid=pos.id, payload=payload, sats=price_msat, pin=decryptedPin
    )
    if not lnurlpospayment:
        return jsonify({"status": "ERROR", "reason": "Could not create payment"})
    resp = LnurlPayResponse(
        callback=url_for(
            "lnurlpos.lnurl_callback",
            paymentid=lnurlpospayment.id,
            _external=True,
        ),
        min_sendable=price_msat,
        max_sendable=price_msat,
        metadata=LnurlPayMetadata(json.dumps([["text/plain", str(pos.title)]])),
    )
    params = resp.dict()
    return jsonify(params)


@lnurlpos_ext.route("/api/v1/lnurl/cb/<paymentid>", methods=["GET"])
async def lnurl_callback(paymentid):
    lnurlpospayment = await get_lnurlpospayment(paymentid)
    pos = await get_lnurlpos(lnurlpospayment.posid)
    if not pos:
        return jsonify({"status": "ERROR", "reason": "lnurlpos not found."})
    payment_hash, payment_request = await create_invoice(
        wallet_id=pos.wallet,
        amount=int(lnurlpospayment.sats / 1000),
        memo=pos.title,
        description_hash=hashlib.sha256(
            (LnurlPayMetadata(json.dumps([["text/plain", str(pos.title)]]))).encode(
                "utf-8"
            )
        ).digest(),
        extra={"tag": "lnurlpos"},
    )
    lnurlpospayment = await update_lnurlpospayment(
        lnurlpospayment_id=paymentid, payhash=payment_hash
    )
    success_action = pos.success_action(paymentid)
    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=success_action,
        disposable=False,
        routes=[],
    )
    return jsonify(resp.dict())
