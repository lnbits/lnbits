import hashlib
import math
from http import HTTPStatus

from fastapi import Request
from lnurl import (  # type: ignore
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayResponse,
)
from loguru import logger
from starlette.requests import Request
from starlette.exceptions import HTTPException

from fastapi.params import Query

from lnbits.core.services import create_invoice
from lnbits.utils.exchange_rates import get_fiat_rate_satoshis

from . import lnaddy_ext
from .crud import increment_pay_link, get_address_data

async def lnurl_response(username: str, domain: str, request: Request):
    address_data = await get_address_data(username)

    if not address_data:
        return {"status": "ERROR", "reason": "Address not found."}

    resp = {
        "tag": "payRequest",
        "callback": request.url_for("lnaddy.api_lnurl_callback", link_id=address_data.id),
        "metadata": await address_data.lnurlpay_metadata(domain=domain),
        "minSendable": address_data.min,
        "maxSendable": address_data.max,
    }

    logger.debug("RESP", resp)
    return resp


@lnaddy_ext.get(
    "/api/v1/lnaddy/{link_id}",
    status_code=HTTPStatus.OK,
    name="lnaddy.api_lnurl_response",
)
async def api_lnurl_response(request: Request, link_id):
    link = await increment_pay_link(link_id, served_meta=1)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )

    rate = await get_fiat_rate_satoshis(link.currency) if link.currency else 1

    resp = LnurlPayResponse(
        callback=request.url_for("lnaddy.api_lnurl_callback", link_id=link.id),
        min_sendable=round(link.min * rate) * 1000,
        max_sendable=round(link.max * rate) * 1000,
        metadata=link.lnurlpay_metadata,
    )
    params = resp.dict()

    if link.comment_chars > 0:
        params["commentAllowed"] = link.comment_chars

    return params


@lnaddy_ext.get(
    "/api/v1/lnaddy/cb/{link_id}",
    status_code=HTTPStatus.OK,
    name="lnaddy.api_lnurl_callback",
)
async def api_lnurl_callback(request: Request, link_id):
    link = await increment_pay_link(link_id, served_pr=1)
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )
    min, max = link.min, link.max
    rate = await get_fiat_rate_satoshis(link.currency) if link.currency else 1
    if link.currency:
        # allow some fluctuation (as the fiat price may have changed between the calls)
        min = rate * 995 * link.min
        max = rate * 1010 * link.max
    else:
        min = link.min * 1000
        max = link.max * 1000

    amount_received = int(request.query_params.get("amount") or 0)
    if amount_received < min:
        return LnurlErrorResponse(
            reason=f"Amount {amount_received} is smaller than minimum {min}."
        ).dict()

    elif amount_received > max:
        return LnurlErrorResponse(
            reason=f"Amount {amount_received} is greater than maximum {max}."
        ).dict()

    comment = request.query_params.get("comment")
    if len(comment or "") > link.comment_chars:
        return LnurlErrorResponse(
            reason=f"Got a comment with {len(comment)} characters, but can only accept {link.comment_chars}"
        ).dict()

    payment_hash, payment_request = await create_invoice(
        wallet_id=link.wallet,
        amount=int(amount_received / 1000),
        memo=link.description,
        unhashed_description=link.lnurlpay_metadata.encode("utf-8"),
        extra={
            "tag": "lnurlp",
            "link": link.id,
            "comment": comment,
            "extra": request.query_params.get("amount"),
        },
    )

    success_action = link.success_action(payment_hash)
    if success_action:
        resp = LnurlPayActionResponse(
            pr=payment_request, success_action=success_action, routes=[]
        )
    else:
        resp = LnurlPayActionResponse(pr=payment_request, routes=[])

    return resp.dict()


# @lnaddy_ext.get("/lnurl/cb/{address_id}", name="lnaddy.lnurl_callback")
# async def lnurl_callback(address_id, amount: int = Query(...)):
#     address = await get_address(address_id)
#     if not address:
#         return LnurlErrorResponse(reason=f"Address not found").dict()

#     amount_received = amount

#     domain = await get_domain(address.domain)

#     base_url = (
#         address.wallet_endpoint[:-1]
#         if address.wallet_endpoint.endswith("/")
#         else address.wallet_endpoint
#     )

#     async with httpx.AsyncClient() as client:
#         try:
#             call = await client.post(
#                 base_url + "/api/v1/payments",
#                 headers={
#                     "X-Api-Key": address.wallet_key,
#                     "Content-Type": "application/json",
#                 },
#                 json={
#                     "out": False,
#                     "amount": int(amount_received / 1000),
#                     "description_hash": (
#                         await address.lnurlpay_metadata(domain=domain.domain)
#                     ).encode("utf-8"),
#                     "extra": {"tag": f"Payment to {address.username}@{domain.domain}"},
#                 },
#                 timeout=40,
#             )

#             r = call.json()
#         except AssertionError as e:
#             return LnurlErrorResponse(reason="ERROR")

#     # resp = LnurlPayActionResponse(pr=r["payment_request"], routes=[])
#     resp = {"pr": r["payment_request"], "routes": []}

#     return resp
