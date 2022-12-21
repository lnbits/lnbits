import json
import traceback
from datetime import datetime
from http import HTTPStatus

import httpx
import shortuuid  # type: ignore
from fastapi import HTTPException
from fastapi.param_functions import Query
from loguru import logger
from starlette.requests import Request
from starlette.responses import HTMLResponse

from lnbits.core.crud import update_payment_extra
from lnbits.core.services import pay_invoice

from . import withdraw_ext
from .crud import get_withdraw_link_by_hash, update_withdraw_link

# FOR LNURLs WHICH ARE NOT UNIQUE


@withdraw_ext.get(
    "/api/v1/lnurl/{unique_hash}",
    response_class=HTMLResponse,
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


# CALLBACK


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

    usescsv = ""

    for x in range(1, link.uses - link.used):
        usecv = link.usescsv.split(",")
        usescsv += "," + str(usecv[x])
    usecsvback = usescsv

    found = False
    if id_unique_hash is not None:
        useslist = link.usescsv.split(",")
        for ind, x in enumerate(useslist):
            tohash = link.id + link.unique_hash + str(x)
            if id_unique_hash == shortuuid.uuid(name=tohash):
                found = True
                useslist.pop(ind)
                usescsv = ",".join(useslist)
        if not found:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="withdraw not found."
            )
    else:
        usescsv = usescsv[1:]

    changesback = {
        "open_time": link.wait_time,
        "used": link.used,
        "usescsv": usecsvback,
    }

    try:
        changes = {
            "open_time": link.wait_time + now,
            "used": link.used + 1,
            "usescsv": usescsv,
        }
        await update_withdraw_link(link.id, **changes)

        payment_request = pr

        payment_hash = await pay_invoice(
            wallet_id=link.wallet,
            payment_request=payment_request,
            max_sat=link.max_withdrawable,
            extra={"tag": "withdraw"},
        )

        if link.webhook_url:
            async with httpx.AsyncClient() as client:
                try:
                    kwargs = {
                        "json": {
                            "payment_hash": payment_hash,
                            "payment_request": payment_request,
                            "lnurlw": link.id,
                        },
                        "timeout": 40,
                    }
                    if link.webhook_body:
                        kwargs["json"]["body"] = json.loads(link.webhook_body)
                    if link.webhook_headers:
                        kwargs["headers"] = json.loads(link.webhook_headers)

                    r: httpx.Response = await client.post(link.webhook_url, **kwargs)
                    await update_payment_extra(
                        payment_hash,
                        dict(
                            {
                                "wh_success": r.is_success,
                                "wh_message": r.reason_phrase,
                                "wh_response": r.text,
                            }
                        ),
                    )
                except Exception as exc:
                    # webhook fails shouldn't cause the lnurlw to fail since invoice is already paid
                    logger.error(
                        "Caught exception when dispatching webhook url: " + str(exc)
                    )
                    await update_payment_extra(
                        payment_hash,
                        dict({"wh_success": False, "wh_message": str(exc)}),
                    )

        return {"status": "OK"}

    except Exception as e:
        await update_withdraw_link(link.id, **changesback)
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=f"withdraw not working. {str(e)}"
        )


# FOR LNURLs WHICH ARE UNIQUE


@withdraw_ext.get(
    "/api/v1/lnurl/{unique_hash}/{id_unique_hash}",
    response_class=HTMLResponse,
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

    useslist = link.usescsv.split(",")
    found = False
    for x in useslist:
        tohash = link.id + link.unique_hash + str(x)
        if id_unique_hash == shortuuid.uuid(name=tohash):
            found = True

    if not found:
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
