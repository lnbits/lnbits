import json
from datetime import datetime
from http import HTTPStatus

import httpx
import shortuuid
from fastapi import HTTPException, Query, Request, Response
from loguru import logger

from lnbits.core.crud import update_payment_extra
from lnbits.core.services import pay_invoice

from . import withdraw_ext
from .crud import (
    get_withdraw_link_by_hash,
    increment_withdraw_link,
    remove_unique_withdraw_link,
)
from .models import WithdrawLink


@withdraw_ext.get(
    "/api/v1/lnurl/{unique_hash}",
    response_class=Response,
    name="withdraw.api_lnurl_response",
)
async def api_lnurl_response(request: Request, unique_hash):
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
        )

    if link.is_spent:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw is spent."
        )
    url = request.url_for("withdraw.api_lnurl_callback", unique_hash=link.unique_hash)
    withdrawResponse = {
        "tag": "withdrawRequest",
        "callback": url,
        "k1": link.k1,
        "minWithdrawable": link.min_withdrawable * 1000,
        "maxWithdrawable": link.max_withdrawable * 1000,
        "defaultDescription": link.title,
        "webhook_url": link.webhook_url,
        "webhook_headers": link.webhook_headers,
        "webhook_body": link.webhook_body,
    }

    return json.dumps(withdrawResponse)


@withdraw_ext.get(
    "/api/v1/lnurl/cb/{unique_hash}",
    name="withdraw.api_lnurl_callback",
    summary="lnurl withdraw callback",
    description="""
        This endpoints allows you to put unique_hash, k1
        and a payment_request to get your payment_request paid.
    """,
    response_description="JSON with status",
    responses={
        200: {"description": "status: OK"},
        400: {"description": "k1 is wrong or link open time or withdraw not working."},
        404: {"description": "withdraw link not found."},
        405: {"description": "withdraw link is spent."},
    },
)
async def api_lnurl_callback(
    unique_hash,
    k1: str = Query(...),
    pr: str = Query(...),
    id_unique_hash=None,
):
    link = await get_withdraw_link_by_hash(unique_hash)
    now = int(datetime.now().timestamp())
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="withdraw not found."
        )

    if link.is_spent:
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="withdraw is spent."
        )

    if link.k1 != k1:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="k1 is wrong.")

    if now < link.open_time:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"wait link open_time {link.open_time - now} seconds.",
        )

    if id_unique_hash:
        if check_unique_link(link, id_unique_hash):
            await remove_unique_withdraw_link(link, id_unique_hash)
        else:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="withdraw not found."
            )

    try:
        payment_hash = await pay_invoice(
            wallet_id=link.wallet,
            payment_request=pr,
            max_sat=link.max_withdrawable,
            extra={"tag": "withdraw"},
        )
        await increment_withdraw_link(link)
        if link.webhook_url:
            await dispatch_webhook(link, payment_hash, pr)
        return {"status": "OK"}
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=f"withdraw not working. {str(e)}"
        )


def check_unique_link(link: WithdrawLink, unique_hash: str) -> bool:
    return any(
        unique_hash == shortuuid.uuid(name=link.id + link.unique_hash + x.strip())
        for x in link.usescsv.split(",")
    )


async def dispatch_webhook(
    link: WithdrawLink, payment_hash: str, payment_request: str
) -> None:
    async with httpx.AsyncClient() as client:
        try:
            r: httpx.Response = await client.post(
                link.webhook_url,
                json={
                    "payment_hash": payment_hash,
                    "payment_request": payment_request,
                    "lnurlw": link.id,
                    "body": json.loads(link.webhook_body) if link.webhook_body else "",
                },
                headers=json.loads(link.webhook_headers)
                if link.webhook_headers
                else None,
                timeout=40,
            )
            await update_payment_extra(
                payment_hash=payment_hash,
                extra={
                    "wh_success": r.is_success,
                    "wh_message": r.reason_phrase,
                    "wh_response": r.text,
                },
                outgoing=True,
            )
        except Exception as exc:
            # webhook fails shouldn't cause the lnurlw to fail since invoice is already paid
            logger.error("Caught exception when dispatching webhook url: " + str(exc))
            await update_payment_extra(
                payment_hash=payment_hash,
                extra={"wh_success": False, "wh_message": str(exc)},
                outgoing=True,
            )


# FOR LNURLs WHICH ARE UNIQUE
@withdraw_ext.get(
    "/api/v1/lnurl/{unique_hash}/{id_unique_hash}",
    response_class=Response,
    name="withdraw.api_lnurl_multi_response",
)
async def api_lnurl_multi_response(request: Request, unique_hash, id_unique_hash):
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-withdraw not found."
        )

    if link.is_spent:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw is spent."
        )

    if not check_unique_link(link, id_unique_hash):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-withdraw not found."
        )

    url = request.url_for("withdraw.api_lnurl_callback", unique_hash=link.unique_hash)
    withdrawResponse = {
        "tag": "withdrawRequest",
        "callback": url + "?id_unique_hash=" + id_unique_hash,
        "k1": link.k1,
        "minWithdrawable": link.min_withdrawable * 1000,
        "maxWithdrawable": link.max_withdrawable * 1000,
        "defaultDescription": link.title,
    }
    return json.dumps(withdrawResponse)
