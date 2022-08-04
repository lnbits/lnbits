import hashlib
import json
import math
from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse  # type: ignore

from lnbits.core.services import create_invoice, pay_invoice

from . import satsdice_ext
from .crud import (
    create_satsdice_payment,
    get_satsdice_pay,
    get_satsdice_withdraw_by_hash,
    update_satsdice_withdraw,
)
from .models import CreateSatsDicePayment

##############LNURLP STUFF


@satsdice_ext.get(
    "/api/v1/lnurlp/{link_id}",
    response_class=HTMLResponse,
    name="satsdice.lnurlp_response",
)
async def api_lnurlp_response(req: Request, link_id: str = Query(None)):
    link = await get_satsdice_pay(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-pay not found."
        )
    payResponse = {
        "tag": "payRequest",
        "callback": req.url_for("satsdice.api_lnurlp_callback", link_id=link.id),
        "metadata": link.lnurlpay_metadata,
        "minSendable": math.ceil(link.min_bet * 1) * 1000,
        "maxSendable": round(link.max_bet * 1) * 1000,
    }
    return json.dumps(payResponse)


@satsdice_ext.get(
    "/api/v1/lnurlp/cb/{link_id}",
    response_class=HTMLResponse,
    name="satsdice.api_lnurlp_callback",
)
async def api_lnurlp_callback(
    req: Request, link_id: str = Query(None), amount: str = Query(None)
):
    link = await get_satsdice_pay(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-pay not found."
        )

    min, max = link.min_bet, link.max_bet
    min = link.min_bet * 1000
    max = link.max_bet * 1000

    amount_received = int(amount or 0)
    if amount_received < min:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=f"Amount {amount_received} is smaller than minimum {min}.",
        )
    elif amount_received > max:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=f"Amount {amount_received} is greater than maximum {max}.",
        )

    payment_hash, payment_request = await create_invoice(
        wallet_id=link.wallet,
        amount=int(amount_received / 1000),
        memo="Satsdice bet",
        description_hash=link.lnurlpay_metadata.encode("utf-8"),
        extra={"tag": "satsdice", "link": link.id, "comment": "comment"},
    )

    success_action = link.success_action(payment_hash=payment_hash, req=req)

    data: CreateSatsDicePayment = {
        "satsdice_pay": link.id,
        "value": amount_received / 1000,
        "payment_hash": payment_hash,
    }

    await create_satsdice_payment(data)
    payResponse = {"pr": payment_request, "successAction": success_action, "routes": []}

    return json.dumps(payResponse)


##############LNURLW STUFF


@satsdice_ext.get(
    "/api/v1/lnurlw/{unique_hash}",
    response_class=HTMLResponse,
    name="satsdice.lnurlw_response",
)
async def api_lnurlw_response(req: Request, unique_hash: str = Query(None)):
    link = await get_satsdice_withdraw_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-satsdice not found."
        )
    if link.used:
        raise HTTPException(status_code=HTTPStatus.OK, detail="satsdice is spent.")
    url = req.url_for("satsdice.api_lnurlw_callback", unique_hash=link.unique_hash)
    withdrawResponse = {
        "tag": "withdrawRequest",
        "callback": url,
        "k1": link.k1,
        "minWithdrawable": link.value * 1000,
        "maxWithdrawable": link.value * 1000,
        "defaultDescription": "Satsdice winnings!",
    }
    return json.dumps(withdrawResponse)


# CALLBACK


@satsdice_ext.get(
    "/api/v1/lnurlw/cb/{unique_hash}",
    status_code=HTTPStatus.OK,
    name="satsdice.api_lnurlw_callback",
)
async def api_lnurlw_callback(
    req: Request,
    unique_hash: str = Query(None),
    k1: str = Query(None),
    pr: str = Query(None),
):

    link = await get_satsdice_withdraw_by_hash(unique_hash)
    if not link:
        return {"status": "ERROR", "reason": "no withdraw"}
    if link.used:
        return {"status": "ERROR", "reason": "spent"}
    paylink = await get_satsdice_pay(link.satsdice_pay)

    await update_satsdice_withdraw(link.id, used=1)
    await pay_invoice(
        wallet_id=paylink.wallet,
        payment_request=pr,
        max_sat=link.value,
        extra={"tag": "withdraw"},
    )

    return {"status": "OK"}
