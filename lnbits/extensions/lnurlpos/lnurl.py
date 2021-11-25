import hashlib
from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from lnurl import LnurlPayActionResponse, LnurlPayResponse  # type: ignore
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
    pos = await get_lnurlpos(pos_id)
    if not pos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurlpos not found."
        )
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
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not an amount.")
    price_msat = (
        await fiat_amount_as_satoshis(decryptedAmount, pos.currency)
        if pos.currency != "sat"
        else pos.currency
    ) * 1000

    lnurlpospayment = await create_lnurlpospayment(
        posid=pos.id,
        payload=payload,
        sats=price_msat,
        pin=decryptedPin,
        payhash="payment_hash",
    )

    if not lnurlpospayment:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Could not create payment"
        )

    resp = LnurlPayResponse(
        callback=request.url_for(
            "lnurlpos.lnurl_callback", paymentid=lnurlpospayment.id
        ),
        min_sendable=price_msat,
        max_sendable=price_msat,
        metadata=await pos.lnurlpay_metadata(),
    )

    return resp.dict()


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

    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=pos.success_action(paymentid, request),
        routes=[],
    )

    return resp.dict()
