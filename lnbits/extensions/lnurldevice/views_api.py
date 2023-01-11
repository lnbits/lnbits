from http import HTTPStatus

from fastapi import Depends, HTTPException, Query, Request

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.utils.exchange_rates import currencies

from . import lnurldevice_ext
from .crud import (
    create_lnurldevice,
    delete_lnurldevice,
    get_lnurldevice,
    get_lnurldevices,
    update_lnurldevice,
)
from .models import createLnurldevice


@lnurldevice_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return list(currencies.keys())


@lnurldevice_ext.post("/api/v1/lnurlpos")
@lnurldevice_ext.put("/api/v1/lnurlpos/{lnurldevice_id}")
async def api_lnurldevice_create_or_update(
    req: Request,
    data: createLnurldevice,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    lnurldevice_id: str = Query(None),
):
    if not lnurldevice_id:
        lnurldevice = await create_lnurldevice(data)
        return {**lnurldevice.dict(), **{"switches": lnurldevice.switches(req)}}
    else:
        lnurldevice = await update_lnurldevice(lnurldevice_id, **data.dict())
        return {**lnurldevice.dict(), **{"switches": lnurldevice.switches(req)}}


@lnurldevice_ext.get("/api/v1/lnurlpos")
async def api_lnurldevices_retrieve(
    req: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    user = await get_user(wallet.wallet.user)
    wallet_ids = user.wallet_ids if user else []
    try:
        return [
            {**lnurldevice.dict(), **{"switches": lnurldevice.switches(req)}}
            for lnurldevice in await get_lnurldevices(wallet_ids)
        ]
    except:
        try:
            return [
                {**lnurldevice.dict()}
                for lnurldevice in await get_lnurldevices(wallet_ids)
            ]
        except:
            return ""


@lnurldevice_ext.get(
    "/api/v1/lnurlpos/{lnurldevice_id}", dependencies=[Depends(get_key_type)]
)
async def api_lnurldevice_retrieve(
    req: Request,
    lnurldevice_id: str = Query(None),
):
    lnurldevice = await get_lnurldevice(lnurldevice_id)
    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurldevice does not exist"
        )
    return {**lnurldevice.dict(), **{"switches": lnurldevice.switches(req)}}


@lnurldevice_ext.delete(
    "/api/v1/lnurlpos/{lnurldevice_id}", dependencies=[Depends(require_admin_key)]
)
async def api_lnurldevice_delete(lnurldevice_id: str = Query(None)):
    lnurldevice = await get_lnurldevice(lnurldevice_id)
    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet link does not exist."
        )

    await delete_lnurldevice(lnurldevice_id)
    return "", HTTPStatus.NO_CONTENT
