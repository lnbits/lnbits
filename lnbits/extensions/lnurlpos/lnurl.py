import json
import hashlib
import math
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore
from lnurl.types import LnurlPayMetadata
from lnbits.core.services import create_invoice
from Crypto.Cipher import AES
from hashlib import md5

from . import lnurlpos_ext
from .crud import get_lnurlpos
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
    print(res)
    decryptedKey = int.from_bytes(res[:2], "little")
    decryptedAmount = int.from_bytes(res[2:6], "little")
    if type(decryptedAmount) != int or float:
        return jsonify({"status": "ERROR", "reason": "Incorrect amount."})
    if decryptedKey != pos.key:
        return jsonify({"status": "ERROR", "reason": "Incorrect key."})
    resp = LnurlPayResponse(
        callback=url_for(
            "lnurlpos.lnurl_callback",
            nonce=nonce,
            payload=payload,
            pos_id=pos_id,
            _external=True,
        ),
        min_sendable=int(fiat_amount_as_satoshis(decryptedAmount, pos.currency)),
        max_sendable=int(fiat_amount_as_satoshis(decryptedAmount, pos.currency)),
        metadata=LnurlPayMetadata(json.dumps([["text/plain", str(pos.lnurl_title)]])),
    )
    params = resp.dict()
    return jsonify(params)


@lnurlpos_ext.route("/api/v1/lnurl/cb/<nonce>/<payload>/<pos_id>", methods=["GET"])
async def lnurl_callback(nonce, payload, pos_id):
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
    print(res)
    decryptedKey = int.from_bytes(res[:2], "little")
    decryptedAmount = int.from_bytes(res[2:6], "little")
    if type(decryptedAmount) != int or float:
        return jsonify({"status": "ERROR", "reason": "Incorrect amount."})
    if decryptedKey != pos.key:
        return jsonify({"status": "ERROR", "reason": "Incorrect key."})

    payment_hash, payment_request = await create_invoice(
        wallet_id=pos.wallet,
        amount=int(fiat_amount_as_satoshis(decryptedAmount, pos.currency) / 1000),
        memo=pos.title,
        description_hash=hashlib.sha256(
            (LnurlPayMetadata(json.dumps([["text/plain", str(pos.title)]]))).encode(
                "utf-8"
            )
        ).digest(),
        extra={"tag": "lnurlpos", "lnurlpos": pos.id, "payload": payload},
    )
    success_action = pos.success_action(payment_hash, nonce)
    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=success_action,
        disposable=False,
        routes=[],
    )
    return jsonify(resp.dict())
