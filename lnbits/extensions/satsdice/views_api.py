from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import satsdice_ext
from .crud import (
    create_satsdice_pay,
    create_satsdice_withdraw,
    delete_satsdice_pay,
    delete_satsdice_withdraw,
    get_satsdice_pay,
    get_satsdice_pays,
    get_satsdice_withdraw,
    get_satsdice_withdraws,
    update_satsdice_pay,
    update_satsdice_withdraw,
)
from .models import CreateSatsDiceLink, CreateSatsDiceWithdraws

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

        return [{**link.dict(), **{"lnurl": link.lnurl(request)}} for link in links]
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
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your pay link."
        )

    return {**link.dict(), **{"lnurl": link.lnurl}}


@satsdice_ext.post("/api/v1/links", status_code=HTTPStatus.CREATED)
@satsdice_ext.put("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
async def api_link_create_or_update(
    data: CreateSatsDiceLink,
    wallet: WalletTypeInfo = Depends(get_key_type),
    link_id: str = Query(None),
):
    if data.min_bet > data.max_bet:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Bad request")
    if link_id:
        link = await get_satsdice_pay(link_id)

        if not link:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Satsdice does not exist"
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

    return {**link.dict(), **{"lnurl": link.lnurl}}


@satsdice_ext.delete("/api/v1/links/{link_id}")
async def api_link_delete(
    wallet: WalletTypeInfo = Depends(get_key_type), link_id: str = Query(None)
):
    link = await get_satsdice_pay(link_id)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pay link does not exist."
        )

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your pay link."
        )

    await delete_satsdice_pay(link_id)

    return "", HTTPStatus.NO_CONTENT


##########LNURL withdraw


@satsdice_ext.get("/api/v1/withdraws/{the_hash}/{lnurl_id}")
async def api_withdraw_hash_retrieve(
    wallet: WalletTypeInfo = Depends(get_key_type),
    lnurl_id: str = Query(None),
    the_hash: str = Query(None),
):
    hashCheck = await get_withdraw_hash_check(the_hash, lnurl_id)
    return hashCheck
