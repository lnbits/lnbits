import json
import traceback
import httpx

from datetime import datetime
from http import HTTPStatus

import shortuuid  # type: ignore
from fastapi import HTTPException
from fastapi.param_functions import Query
from starlette.requests import Request
from starlette.responses import HTMLResponse  # type: ignore

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
        raise HTTPException(detail="Withdraw is spent.")
    url = request.url_for("withdraw.api_lnurl_callback", unique_hash=link.unique_hash)
    withdrawResponse = {
        "tag": "withdrawRequest",
        "callback": url,
        "k1": link.k1,
        "minWithdrawable": link.min_withdrawable * 1000,
        "maxWithdrawable": link.max_withdrawable * 1000,
        "defaultDescription": link.title,
    }
    return json.dumps(withdrawResponse)


# CALLBACK


@withdraw_ext.get("/api/v1/lnurl/cb/{unique_hash}", name="withdraw.api_lnurl_callback")
async def api_lnurl_callback(
    unique_hash, request: Request, k1: str = Query(...), pr: str = Query(...)
):
    link = await get_withdraw_link_by_hash(unique_hash)
    now = int(datetime.now().timestamp())
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-withdraw not found"
        )

    if link.is_spent:
        raise HTTPException(status_code=HTTPStatus.OK, detail="Withdraw is spent.")

    if link.k1 != k1:
        raise HTTPException(status_code=HTTPStatus.OK, detail="Bad request.")

    if now < link.open_time:
        return {"status": "ERROR", "reason": f"Wait {link.open_time - now} seconds."}

    try:
        usescsv = ""
        for x in range(1, link.uses - link.used):
            usecv = link.usescsv.split(",")
            usescsv += "," + str(usecv[x])
        usecsvback = usescsv
        usescsv = usescsv[1:]

        changesback = {
            "open_time": link.wait_time,
            "used": link.used,
            "usescsv": usecsvback,
        }

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
                    r = await client.post(
                        link.webhook_url,
                        json={
                            "payment_hash": payment_hash,
                            "payment_request": payment_request,
                            "lnurlw": link.id,
                        },
                        timeout=40,
                    )
                except Exception as exc:
                    # webhook fails shouldn't cause the lnurlw to fail since invoice is already paid
                    print("Caught exception when dispatching webhook url:", exc)

        return {"status": "OK"}

    except Exception as e:
        await update_withdraw_link(link.id, **changesback)
        print(traceback.format_exc())
        return {"status": "ERROR", "reason": "Link not working"}


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
            status_code=HTTPStatus.OK, detail="LNURL-withdraw not found."
        )

    if link.is_spent:
        raise HTTPException(status_code=HTTPStatus.OK, detail="Withdraw is spent.")

    useslist = link.usescsv.split(",")
    found = False
    for x in useslist:
        tohash = link.id + link.unique_hash + str(x)
        if id_unique_hash == shortuuid.uuid(name=tohash):
            found = True
    if not found:
        raise HTTPException(
            status_code=HTTPStatus.OK, detail="LNURL-withdraw not found."
        )

    url = request.url_for("withdraw.api_lnurl_callback", unique_hash=link.unique_hash)
    withdrawResponse = {
        "tag": "withdrawRequest",
        "callback": url,
        "k1": link.k1,
        "minWithdrawable": link.min_withdrawable * 1000,
        "maxWithdrawable": link.max_withdrawable * 1000,
        "defaultDescription": link.title,
    }
    return json.dumps(withdrawResponse)
