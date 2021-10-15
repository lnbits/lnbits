from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore
from http import HTTPStatus
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
from lnbits.core.crud import get_user
from lnbits.decorators import api_validate_post_request
from .models import CreateSatsDiceLink, CreateSatsDiceWithdraws, CreateSatsDicePayment
from . import satsdice_ext
from fastapi import FastAPI, Request
from fastapi.params import Depends
from typing import Optional
from fastapi.param_functions import Query
from .crud import (
    create_satsdice_pay,
    get_satsdice_pay,
    get_satsdice_pays,
    update_satsdice_pay,
    delete_satsdice_pay,
    create_satsdice_withdraw,
    get_satsdice_withdraw,
    get_satsdice_withdraws,
    update_satsdice_withdraw,
    delete_satsdice_withdraw,
    create_withdraw_hash_check,
)
from lnbits.decorators import (
    check_user_exists,
    WalletTypeInfo,
    get_key_type,
    api_validate_post_request,
)

################LNURL pay


@satsdice_ext.get("/api/v1/links")
async def api_links(
    request: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    all_wallets: str = Query(None),
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    try:
        links = await get_satsdice_pays(wallet_ids)
        print(links[0])

        return [{link.dict(), {"lnurl": link.lnurl(request)}} for link in links]
    except LnurlInvalidUrl:
        raise HTTPException(
            status_code=HTTPStatus.UPGRADE_REQUIRED,
            detail="LNURLs need to be delivered over a publically accessible `https` domain or Tor.",
        )


@satsdice_ext.get("/api/v1/links/{link_id}")
async def api_link_retrieve(
    data: CreateSatsDiceLink,
    link_id: str = Query(None),
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    link = await get_satsdice_pay(link_id)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Pay link does not exist.",
        )

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not your pay link.",
        )

    return {**link._asdict(), **{"lnurl": link.lnurl}}


@satsdice_ext.post("/api/v1/links", status_code=HTTPStatus.CREATED)
@satsdice_ext.put("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
async def api_link_create_or_update(
    data: CreateSatsDiceLink,
    wallet: WalletTypeInfo = Depends(get_key_type),
    link_id: str = Query(None),
):
    if data.min_bet > data.max_bet:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Bad request",
        )
    if link_id:
        link = await get_satsdice_pay(link_id)

        if not link:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Satsdice does not exist",
            )

        if link.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Come on, seriously, this isn't your satsdice!",
            )
        data.link_id = link_id
        link = await update_satsdice_pay(data)
    else:
        data.wallet_id = wallet.wallet.id
        link = await create_satsdice_pay(data)

    return {link.dict(), {"lnurl": link.lnurl}}


@satsdice_ext.delete("/api/v1/links/{link_id}")
async def api_link_delete(
    wallet: WalletTypeInfo = Depends(get_key_type), link_id: str = Query(None)
):
    link = await get_satsdice_pay(link_id)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Pay link does not exist.",
        )

    if link.wallet != g.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not your pay link.",
        )

    await delete_satsdice_pay(link_id)

    return "", HTTPStatus.NO_CONTENT


##########LNURL withdraw


@satsdice_ext.get("/api/v1/withdraws")
async def api_withdraws(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: str = Query(None)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    try:
        return (
            jsonify(
                [
                    {
                        **withdraw._asdict(),
                        **{"lnurl": withdraw.lnurl},
                    }
                    for withdraw in await get_satsdice_withdraws(wallet_ids)
                ]
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        raise HTTPException(
            status_code=HTTPStatus.UPGRADE_REQUIRED,
            detail="LNURLs need to be delivered over a publically accessible `https` domain or Tor.",
        )


@satsdice_ext.get("/api/v1/withdraws/{withdraw_id}")
async def api_withdraw_retrieve(
    wallet: WalletTypeInfo = Depends(get_key_type), withdraw_id: str = Query(None)
):
    withdraw = await get_satsdice_withdraw(withdraw_id, 0)

    if not withdraw:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="satsdice withdraw does not exist.",
        )

    if withdraw.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not your satsdice withdraw.",
        )

    return {**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}, HTTPStatus.OK


@satsdice_ext.post("/api/v1/withdraws", status_code=HTTPStatus.CREATED)
@satsdice_ext.put("/api/v1/withdraws/{withdraw_id}", status_code=HTTPStatus.OK)
async def api_withdraw_create_or_update(
    data: CreateSatsDiceWithdraws,
    wallet: WalletTypeInfo = Depends(get_key_type),
    withdraw_id: str = Query(None),
):
    if data.max_satsdiceable < data.min_satsdiceable:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="`max_satsdiceable` needs to be at least `min_satsdiceable`.",
        )

    usescsv = ""
    for i in range(data.uses):
        if data.is_unique:
            usescsv += "," + str(i + 1)
        else:
            usescsv += "," + str(1)
    usescsv = usescsv[1:]

    if withdraw_id:
        withdraw = await get_satsdice_withdraw(withdraw_id, 0)
        if not withdraw:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="satsdice withdraw does not exist.",
            )
        if withdraw.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Not your satsdice withdraw.",
            )

        withdraw = await update_satsdice_withdraw(
            withdraw_id, **data, usescsv=usescsv, used=0
        )
    else:
        withdraw = await create_satsdice_withdraw(
            wallet_id=wallet.wallet.id, **data, usescsv=usescsv
        )

    return {**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}


@satsdice_ext.delete("/api/v1/withdraws/{withdraw_id}")
async def api_withdraw_delete(
    data: CreateSatsDiceWithdraws,
    wallet: WalletTypeInfo = Depends(get_key_type),
    withdraw_id: str = Query(None),
):
    withdraw = await get_satsdice_withdraw(withdraw_id)

    if not withdraw:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="satsdice withdraw does not exist.",
        )

    if withdraw.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not your satsdice withdraw.",
        )

    await delete_satsdice_withdraw(withdraw_id)

    return "", HTTPStatus.NO_CONTENT


@satsdice_ext.get("/api/v1/withdraws/{the_hash}/{lnurl_id}")
async def api_withdraw_hash_retrieve(
    wallet: WalletTypeInfo = Depends(get_key_type),
    lnurl_id: str = Query(None),
    the_hash: str = Query(None),
):
    hashCheck = await get_withdraw_hash_check(the_hash, lnurl_id)
    return hashCheck
