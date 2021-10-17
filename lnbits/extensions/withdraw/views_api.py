from fastapi.params import Depends
from fastapi.param_functions import Query
from pydantic.main import BaseModel

from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type
from .models import CreateWithdrawData

# from fastapi import FastAPI, Query, Response

from . import withdraw_ext
from .crud import (
    create_withdraw_link,
    get_withdraw_link,
    get_withdraw_links,
    update_withdraw_link,
    delete_withdraw_link,
    create_hash_check,
    get_hash_check,
)


@withdraw_ext.get("/api/v1/links", status_code=HTTPStatus.OK)
# @api_check_wallet_key("invoice")
async def api_links(
    req: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    try:
        return [
            {**link.dict(), **{"lnurl": link.lnurl(req)}}
            for link in await get_withdraw_links(wallet_ids)
        ]

    except LnurlInvalidUrl:
        raise HTTPException(
            status_code=HTTPStatus.UPGRADE_REQUIRED,
            detail="LNURLs need to be delivered over a publically accessible `https` domain or Tor.",
        )
        # response.status_code = HTTPStatus.UPGRADE_REQUIRED
        # return { "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor." }


@withdraw_ext.get("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
# @api_check_wallet_key("invoice")
async def api_link_retrieve(link_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    link = await get_withdraw_link(link_id, 0)

    if not link:
        raise HTTPException(
            detail="Withdraw link does not exist.", status_code=HTTPStatus.NOT_FOUND
        )
        # response.status_code = HTTPStatus.NOT_FOUND
        # return {"message": "Withdraw link does not exist."}

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your withdraw link.", status_code=HTTPStatus.FORBIDDEN
        )
        # response.status_code = HTTPStatus.FORBIDDEN
        # return {"message": "Not your withdraw link."}
    return {**link, **{"lnurl": link.lnurl(request)}}


# class CreateData(BaseModel):
#     title:  str = Query(...)
#     min_withdrawable:  int = Query(..., ge=1)
#     max_withdrawable:  int = Query(..., ge=1)
#     uses:  int = Query(..., ge=1)
#     wait_time:  int = Query(..., ge=1)
#     is_unique:  bool


@withdraw_ext.post("/api/v1/links", status_code=HTTPStatus.CREATED)
@withdraw_ext.put("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
# @api_check_wallet_key("admin")
async def api_link_create_or_update(
    req: Request,
    data: CreateWithdrawData,
    link_id: str = None,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    if data.max_withdrawable < data.min_withdrawable:
        raise HTTPException(
            detail="`max_withdrawable` needs to be at least `min_withdrawable`.",
            status_code=HTTPStatus.BAD_REQUEST,
        )
        # response.status_code = HTTPStatus.BAD_REQUEST
        # return {
        #             "message": "`max_withdrawable` needs to be at least `min_withdrawable`."
        #         }

    usescsv = ""
    for i in range(data.uses):
        if data.is_unique:
            usescsv += "," + str(i + 1)
        else:
            usescsv += "," + str(1)
    usescsv = usescsv[1:]

    if link_id:
        link = await get_withdraw_link(link_id, 0)
        if not link:
            raise HTTPException(
                detail="Withdraw link does not exist.", status_code=HTTPStatus.NOT_FOUND
            )
            # response.status_code = HTTPStatus.NOT_FOUND
            # return {"message": "Withdraw link does not exist."}
        if link.wallet != wallet.wallet.id:
            raise HTTPException(
                detail="Not your withdraw link.", status_code=HTTPStatus.FORBIDDEN
            )
            # response.status_code = HTTPStatus.FORBIDDEN
            # return {"message": "Not your withdraw link."}
        link = await update_withdraw_link(link_id, data=data, usescsv=usescsv, used=0)
    else:
        link = await create_withdraw_link(
            wallet_id=wallet.wallet.id, data=data, usescsv=usescsv
        )
    # if link_id:
    #     response.status_code = HTTPStatus.OK
    return {**link.dict(), **{"lnurl": link.lnurl(req)}}


@withdraw_ext.delete("/api/v1/links/{link_id}")
# @api_check_wallet_key("admin")
async def api_link_delete(link_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    link = await get_withdraw_link(link_id)

    if not link:
        raise HTTPException(
            detail="Withdraw link does not exist.", status_code=HTTPStatus.NOT_FOUND
        )
        # response.status_code = HTTPStatus.NOT_FOUND
        # return {"message": "Withdraw link does not exist."}

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your withdraw link.", status_code=HTTPStatus.FORBIDDEN
        )
        # response.status_code = HTTPStatus.FORBIDDEN
        # return {"message": "Not your withdraw link."}

    await delete_withdraw_link(link_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
    # return ""


@withdraw_ext.get("/api/v1/links/{the_hash}/{lnurl_id}", status_code=HTTPStatus.OK)
# @api_check_wallet_key("invoice")
async def api_hash_retrieve(
    the_hash, lnurl_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    hashCheck = await get_hash_check(the_hash, lnurl_id)
    return hashCheck
