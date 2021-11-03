import json
import hashlib
import math
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore
from lnurl.types import LnurlPayMetadata
from lnbits.core.services import create_invoice
from hashlib import md5
from fastapi import Request
from fastapi.param_functions import Query
from . import lnurlpos_ext
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from http import HTTPStatus
from fastapi.params import Depends
from fastapi.param_functions import Query
from .crud import (
    get_lnurlpos,
    create_lnurlpospayment,
    get_lnurlpospayment,
    update_lnurlpospayment,
)
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis


@lnurlpos_ext.get(
    "/api/v1/lnurl/{nonce}/{payload}/{pos_id}",
    response_class=HTMLResponse,
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
    print(price_msat)
    if not lnurlpospayment:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Could not create payment"
        )

    payResponse = {
        "tag": "payRequest",
        "callback": request.url_for(
            "lnurlpos.lnurl_callback",
            paymentid=lnurlpospayment.id,
        ),
        "metadata": LnurlPayMetadata(json.dumps([["text/plain", str(pos.title)]])),
        "minSendable": price_msat,
        "maxSendable": price_msat,
    }
    print(payResponse)
    return json.dumps(payResponse)


@lnurlpos_ext.get(
    "/api/v1/lnurl/cb/{paymentid}",
    response_class=HTMLResponse,
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
            (LnurlPayMetadata(json.dumps([["text/plain", str(pos.title)]]))).encode(
                "utf-8"
            )
        ).digest(),
        extra={"tag": "lnurlpos"},
    )
    lnurlpospayment = await update_lnurlpospayment(
        lnurlpospayment_id=paymentid, payhash=payment_hash
    )
    success_action = pos.success_action(paymentid, request)

    payResponse = {
        "pr": payment_request,
        "success_action": success_action,
        "disposable": False,
        "routes": [],
    }
    return json.dumps(payResponse)
