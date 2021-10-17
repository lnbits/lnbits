import shortuuid  # type: ignore
import hashlib
import math
from http import HTTPStatus
from datetime import datetime
from lnbits.core.services import pay_invoice, create_invoice
from http import HTTPStatus
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
from lnbits.utils.exchange_rates import get_fiat_rate_satoshis
from fastapi import FastAPI, Request
from fastapi.params import Depends
from typing import Optional
from fastapi.param_functions import Query
from . import satsdice_ext
from .crud import (
    get_satsdice_withdraw_by_hash,
    update_satsdice_withdraw,
    get_satsdice_pay,
    create_satsdice_payment,
)
from lnurl import (
    LnurlPayResponse,
    LnurlPayActionResponse,
    LnurlErrorResponse,
)  # type: ignore


##############LNURLP STUFF


@satsdice_ext.get("/api/v1/lnurlp/{link_id}", name="satsdice.lnurlp_response")
async def api_lnurlp_response(req: Request, link_id: str = Query(None)):
    link = await get_satsdice_pay(link_id)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-pay not found."
        )
    resp = LnurlPayResponse(
        callback=req.url_for(
            "satsdice.api_lnurlp_callback", link_id=link.id, _external=True
        ),
        min_sendable=math.ceil(link.min_bet * 1) * 1000,
        max_sendable=round(link.max_bet * 1) * 1000,
        metadata=link.lnurlpay_metadata,
    )
    params = resp.dict()

    return params


@satsdice_ext.get("/api/v1/lnurlp/cb/{link_id}")
async def api_lnurlp_callback(link_id: str = Query(None), amount: str = Query(None)):
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
        return LnurlErrorResponse(
            reason=f"Amount {amount_received} is smaller than minimum {min}."
        ).dict()
    elif amount_received > max:
        return LnurlErrorResponse(
            reason=f"Amount {amount_received} is greater than maximum {max}."
        ).dict()

    payment_hash, payment_request = await create_invoice(
        wallet_id=link.wallet,
        amount=int(amount_received / 1000),
        memo="Satsdice bet",
        description_hash=hashlib.sha256(
            link.lnurlpay_metadata.encode("utf-8")
        ).digest(),
        extra={"tag": "satsdice", "link": link.id, "comment": "comment"},
    )

    success_action = link.success_action(payment_hash)
    data = []
    data.satsdice_payy = link.id
    data.value = amount_received / 1000
    data.payment_hash = payment_hash
    link = await create_satsdice_payment(data)
    if success_action:
        resp = LnurlPayActionResponse(
            pr=payment_request, success_action=success_action, routes=[]
        )
    else:
        resp = LnurlPayActionResponse(pr=payment_request, routes=[])

    return resp.dict()


##############LNURLW STUFF


@satsdice_ext.get("/api/v1/lnurlw/{unique_hash}", name="satsdice.lnurlw_response")
async def api_lnurlw_response(unique_hash: str = Query(None)):
    link = await get_satsdice_withdraw_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-satsdice not found."
        )

    if link.used:
        raise HTTPException(status_code=HTTPStatus.OK, detail="satsdice is spent.")

    return link.lnurl_response.dict()


# CALLBACK


@satsdice_ext.get("/api/v1/lnurlw/cb/{unique_hash}")
async def api_lnurlw_callback(
    unique_hash: str = Query(None), k1: str = Query(None), pr: str = Query(None)
):
    link = await get_satsdice_withdraw_by_hash(unique_hash)
    paylink = await get_satsdice_pay(link.satsdice_pay)
    payment_request = pr
    now = int(datetime.now().timestamp())

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-satsdice not found."
        )

    if link.used:
        raise HTTPException(status_code=HTTPStatus.OK, detail="satsdice is spent.")

    if link.k1 != k1:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Bad request..")

    if now < link.open_time:
        return {"status": "ERROR", "reason": f"Wait {link.open_time - now} seconds."}

    try:
        await update_satsdice_withdraw(link.id, used=1)

        await pay_invoice(
            wallet_id=paylink.wallet,
            payment_request=payment_request,
            max_sat=link.value,
            extra={"tag": "withdraw"},
        )

    except ValueError as e:
        await update_satsdice_withdraw(link.id, used=1)
        return {"status": "ERROR", "reason": str(e)}
    except PermissionError:
        await update_satsdice_withdraw(link.id, used=1)
        return {"status": "ERROR", "reason": "satsdice link is empty."}
    except Exception as e:
        await update_satsdice_withdraw(link.id, used=1)
        return {"status": "ERROR", "reason": str(e)}

    return {"status": "OK"}
