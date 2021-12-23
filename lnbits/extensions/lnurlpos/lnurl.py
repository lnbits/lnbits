import base64
import hashlib
from http import HTTPStatus
from typing import Optional

from embit import bech32
from embit import compact
import base64
from io import BytesIO
import hmac

from fastapi import Request
from fastapi.param_functions import Query
from starlette.exceptions import HTTPException

from lnbits.core.services import create_invoice
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

from . import lnurlpos_ext
from .crud import (
    create_lnurlpospayment,
    get_lnurlpos,
    get_lnurlpospayment,
    update_lnurlpospayment,
)


def bech32_decode(bech):
    """tweaked version of bech32_decode that ignores length limitations"""
    if (any(ord(x) < 33 or ord(x) > 126 for x in bech)) or (
        bech.lower() != bech and bech.upper() != bech
    ):
        return
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech):
        return
    if not all(x in bech32.CHARSET for x in bech[pos + 1 :]):
        return
    hrp = bech[:pos]
    data = [bech32.CHARSET.find(x) for x in bech[pos + 1 :]]
    encoding = bech32.bech32_verify_checksum(hrp, data)
    if encoding is None:
        return
    return bytes(bech32.convertbits(data[:-6], 5, 8, False))


def xor_decrypt(key, blob):
    s = BytesIO(blob)
    variant = s.read(1)[0]
    if variant != 1:
        raise RuntimeError("Not implemented")
    # reading nonce
    l = s.read(1)[0]
    nonce = s.read(l)
    if len(nonce) != l:
        raise RuntimeError("Missing nonce bytes")
    if l < 8:
        raise RuntimeError("Nonce is too short")
    # reading payload
    l = s.read(1)[0]
    payload = s.read(l)
    if len(payload) > 32:
        raise RuntimeError("Payload is too long for this encryption method")
    if len(payload) != l:
        raise RuntimeError("Missing payload bytes")
    hmacval = s.read()
    expected = hmac.new(
        key, b"Data:" + blob[: -len(hmacval)], digestmod="sha256"
    ).digest()
    if len(hmacval) < 8:
        raise RuntimeError("HMAC is too short")
    if hmacval != expected[: len(hmacval)]:
        raise RuntimeError("HMAC is invalid")
    secret = hmac.new(key, b"Round secret:" + nonce, digestmod="sha256").digest()
    payload = bytearray(payload)
    for i in range(len(payload)):
        payload[i] = payload[i] ^ secret[i]
    s = BytesIO(payload)
    pin = compact.read_from(s)
    amount_in_cent = compact.read_from(s)
    return pin, amount_in_cent


@lnurlpos_ext.get(
    "/api/v1/lnurl/{pos_id}",
    status_code=HTTPStatus.OK,
    name="lnurlpos.lnurl_v1_params",
)
async def lnurl_v1_params(
    request: Request,
    pos_id: str = Query(None),
    p: str = Query(None),
):
    pos = await get_lnurlpos(pos_id)
    if not pos:
        return {
            "status": "ERROR",
            "reason": f"lnurlpos {pos_id} not found on this server",
        }

    if len(payload) % 4 > 0:
        payload += "=" * (4 - (len(payload) % 4))

    data = base64.urlsafe_b64decode(payload)
    pin = 0
    amount_in_cent = 0
    try:
        result = xor_decrypt(pos.key.encode(), data)
        pin = result[0]
        amount_in_cent = result[1]
    except Exception as exc:
        return {"status": "ERROR", "reason": str(exc)}

    price_msat = (
        await fiat_amount_as_satoshis(float(amount_in_cent) / 100, pos.currency)
        if pos.currency != "sat"
        else amount_in_cent
    ) * 1000

    lnurlpospayment = await create_lnurlpospayment(
        posid=pos.id,
        payload=payload,
        sats=price_msat,
        pin=pin,
        payhash="payment_hash",
    )
    if not lnurlpospayment:
        return {"status": "ERROR", "reason": "Could not create payment."}

    return {
        "tag": "payRequest",
        "callback": request.url_for(
            "lnurlpos.lnurl_callback", paymentid=lnurlpospayment.id
        ),
        "minSendable": price_msat,
        "maxSendable": price_msat,
        "metadata": await pos.lnurlpay_metadata(),
    }


@lnurlpos_ext.get(
    "/api/v1/lnurl/cb/{paymentid}",
    status_code=HTTPStatus.OK,
    name="lnurlpos.lnurl_callback",
)
async def lnurl_callback(request: Request, paymentid: str = Query(None)):
    lnurlpospayment = await get_lnurlpospayment(paymentid)
    pos = await get_lnurlpos(lnurlpospayment.posid)
    if not pos:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="lnurlpos not found."
        )
    payment_hash, payment_request = await create_invoice(
        wallet_id=pos.wallet,
        amount=int(lnurlpospayment.sats / 1000),
        memo=pos.title,
        description_hash=hashlib.sha256(
            (await pos.lnurlpay_metadata()).encode("utf-8")
        ).digest(),
        extra={"tag": "lnurlpos"},
    )
    lnurlpospayment = await update_lnurlpospayment(
        lnurlpospayment_id=paymentid, payhash=payment_hash
    )

    return {
        "pr": payment_request,
        "successAction": {
            "tag": "url",
            "description": "Check the attached link",
            "url": request.url_for("lnurlpos.displaypin", paymentid=paymentid),
        },
        "routes": [],
    }

    return resp.dict()
