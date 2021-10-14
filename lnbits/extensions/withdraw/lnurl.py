from fastapi.param_functions import Query
from fastapi import HTTPException
import shortuuid  # type: ignore
from http import HTTPStatus
from datetime import datetime

from lnbits.core.services import pay_invoice
from starlette.requests import Request

from . import withdraw_ext
from .crud import get_withdraw_link_by_hash, update_withdraw_link


# FOR LNURLs WHICH ARE NOT UNIQUE


@withdraw_ext.get("/api/v1/lnurl/{unique_hash}", status_code=HTTPStatus.OK, name="withdraw.api_lnurl_response")
async def api_lnurl_response(request: Request, unique_hash):
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Withdraw link does not exist."
        )
        # return ({"status": "ERROR", "reason": "LNURL-withdraw not found."},
        #     HTTPStatus.OK,
        # )

    if link.is_spent:
        raise HTTPException(
            # WHAT STATUS_CODE TO USE??
            detail="Withdraw is spent."
        )
        # return ({"status": "ERROR", "reason": "Withdraw is spent."},
        #     HTTPStatus.OK,
        # )

    return link.lnurl_response(request).dict()



# CALLBACK


@withdraw_ext.get("/api/v1/lnurl/cb/{unique_hash}", name="withdraw.api_lnurl_callback")
async def api_lnurl_callback(request: Request,
        unique_hash: str=Query(...),
        k1: str = Query(...),
        payment_request: str = Query(..., alias="pr")
    ):
    link = await get_withdraw_link_by_hash(unique_hash)
    now = int(datetime.now().timestamp())

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="LNURL-withdraw not found."
        )
        # return (
        #     {"status": "ERROR", "reason": "LNURL-withdraw not found."},
        #     HTTPStatus.OK,
        # )

    if link.is_spent:
        raise HTTPException(
            # WHAT STATUS_CODE TO USE??
            detail="Withdraw is spent."
        )
        # return (
        #     {"status": "ERROR", "reason": "Withdraw is spent."},
        #     HTTPStatus.OK,
        # )

    if link.k1 != k1:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Bad request."
        )
        # return {"status": "ERROR", "reason": "Bad request."}, HTTPStatus.OK

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

        await pay_invoice(
            wallet_id=link.wallet,
            payment_request=payment_request,
            max_sat=link.max_withdrawable,
            extra={"tag": "withdraw"},
        )
    # should these be "raise" instead of the "return" ??
    except ValueError as e:
        await update_withdraw_link(link.id, **changesback)
        return {"status": "ERROR", "reason": str(e)}
    except PermissionError:
        await update_withdraw_link(link.id, **changesback)
        return {"status": "ERROR", "reason": "Withdraw link is empty."}
    except Exception as e:
        await update_withdraw_link(link.id, **changesback)
        return {"status": "ERROR", "reason": str(e)}

    return {"status": "OK"}

# FOR LNURLs WHICH ARE UNIQUE


@withdraw_ext.get("/api/v1/lnurl/{unique_hash}/{id_unique_hash}", status_code=HTTPStatus.OK, name="withdraw.api_lnurl_multi_response")
async def api_lnurl_multi_response(request: Request, unique_hash, id_unique_hash):
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="LNURL-withdraw not found."
        )
        # return (
        #     {"status": "ERROR", "reason": "LNURL-withdraw not found."},
        #     HTTPStatus.OK,
        # )

    if link.is_spent:
        raise HTTPException(
            # WHAT STATUS_CODE TO USE??
            detail="Withdraw is spent."
        )
        # return (
        #     {"status": "ERROR", "reason": "Withdraw is spent."},
        #     HTTPStatus.OK,
        # )

    useslist = link.usescsv.split(",")
    found = False
    for x in useslist:
        tohash = link.id + link.unique_hash + str(x)
        if id_unique_hash == shortuuid.uuid(name=tohash):
            found = True
    if not found:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="LNURL-withdraw not found."
        )
        # return (
        #     {"status": "ERROR", "reason": "LNURL-withdraw not found."},
        #     HTTPStatus.OK,
        # )

    return link.lnurl_response(request).dict()
