import base64
import hashlib
from http import HTTPStatus
from typing import Optional

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


@lnurlpos_ext.get(
    "/api/v1/lnurl/{nonce}/{payload}/{pos_id}",
    status_code=HTTPStatus.OK,
    name="lnurlpos.lnurl_response",
)
async def lnurl_response(
    request: Request,
    nonce: str = Query(None),
    pos_id: str = Query(None),
    payload: str = Query(None),
):
    return await handle_lnurl_firstrequest(
        request, pos_id, nonce, payload, verify_checksum=False
    )


@lnurlpos_ext.get(
    "/api/v2/lnurl/{pos_id}",
    status_code=HTTPStatus.OK,
    name="lnurlpos.lnurl_v2_params",
)
async def lnurl_v2_params(
    request: Request,
    pos_id: str = Query(None),
    n: str = Query(None),
    p: str = Query(None),
):
    return await handle_lnurl_firstrequest(request, pos_id, n, p, verify_checksum=True)


async def handle_lnurl_firstrequest(
    request: Request, pos_id: str, nonce: str, payload: str, verify_checksum: bool
):
    pos = await get_lnurlpos(pos_id)
    if not pos:
        return {
            "status": "ERROR",
            "reason": f"lnurlpos {pos_id} not found on this server",
        }

    try:
        nonceb = bytes.fromhex(nonce)
    except ValueError:
        try:
            nonce += "=" * ((4 - len(nonce) % 4) % 4)
            nonceb = base64.urlsafe_b64decode(nonce)
        except:
            return {
                "status": "ERROR",
                "reason": f"Invalid hex or base64 nonce: {nonce}",
            }

    try:
        payloadb = bytes.fromhex(payload)
    except ValueError:
        try:
            payload += "=" * ((4 - len(payload) % 4) % 4)
            payloadb = base64.urlsafe_b64decode(payload)
        except:
            return {
                "status": "ERROR",
                "reason": f"Invalid hex or base64 payload: {payload}",
            }

    # check payload and nonce sizes
    if len(payloadb) != 8 or len(nonceb) != 8:
        return {"status": "ERROR", "reason": "Expected 8 bytes"}

    # verify hmac
    if verify_checksum:
        expected = hmac.new(
            pos.key.encode(), payloadb[:-2], digestmod="sha256"
        ).digest()
        if expected[:2] != payloadb[-2:]:
            return {"status": "ERROR", "reason": "Invalid HMAC"}

    # decrypt
    s = hmac.new(pos.key.encode(), nonceb, digestmod="sha256").digest()
    res = bytearray(payloadb)
    for i in range(len(res)):
        res[i] = res[i] ^ s[i]

    pin = int.from_bytes(res[0:2], "little")
    amount = int.from_bytes(res[2:6], "little")

    price_msat = (
        await fiat_amount_as_satoshis(float(amount) / 100, pos.currency)
        if pos.currency != "sat"
        else amount
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
            "url": req.url_for("lnurlpos.displaypin", paymentid=paymentid),
        },
        "routes": [],
    }

    return resp.dict()
