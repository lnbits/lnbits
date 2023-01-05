from datetime import datetime, timedelta

import httpx
from fastapi import Query, Request
from lnurl import LnurlErrorResponse
from loguru import logger

from . import lnaddress_ext
from .crud import get_address, get_address_by_username, get_domain


async def lnurl_response(username: str, domain: str, request: Request):
    address = await get_address_by_username(username, domain)

    if not address:
        return {"status": "ERROR", "reason": "Address not found."}

    ## CHECK IF USER IS STILL VALID/PAYING
    now = datetime.now().timestamp()
    start = datetime.fromtimestamp(address.time)
    expiration = (start + timedelta(days=address.duration)).timestamp()

    if now > expiration:
        return LnurlErrorResponse(reason="Address has expired.").dict()

    resp = {
        "tag": "payRequest",
        "callback": request.url_for("lnaddress.lnurl_callback", address_id=address.id),
        "metadata": await address.lnurlpay_metadata(domain=domain),
        "minSendable": 1000,
        "maxSendable": 1000000000,
    }

    logger.debug("RESP", resp)
    return resp


@lnaddress_ext.get("/lnurl/cb/{address_id}", name="lnaddress.lnurl_callback")
async def lnurl_callback(address_id, amount: int = Query(...)):
    address = await get_address(address_id)
    if not address:
        return LnurlErrorResponse(reason=f"Address not found").dict()

    amount_received = amount

    domain = await get_domain(address.domain)
    assert domain

    base_url = (
        address.wallet_endpoint[:-1]
        if address.wallet_endpoint.endswith("/")
        else address.wallet_endpoint
    )

    async with httpx.AsyncClient() as client:
        try:
            call = await client.post(
                base_url + "/api/v1/payments",
                headers={
                    "X-Api-Key": address.wallet_key,
                    "Content-Type": "application/json",
                },
                json={
                    "out": False,
                    "amount": int(amount_received / 1000),
                    "description_hash": (
                        await address.lnurlpay_metadata(domain=domain.domain)
                    ).encode(),
                    "extra": {"tag": f"Payment to {address.username}@{domain.domain}"},
                },
                timeout=40,
            )

            r = call.json()
        except Exception:
            return LnurlErrorResponse(reason="ERROR")

    # resp = LnurlPayActionResponse(pr=r["payment_request"], routes=[])
    resp = {"pr": r["payment_request"], "routes": []}

    return resp
