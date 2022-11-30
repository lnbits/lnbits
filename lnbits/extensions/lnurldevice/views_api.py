from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.lnurldevice import lnurldevice_ext
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


#######################lnurldevice##########################


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
        return {**lnurldevice.dict(), **{"lnurl": lnurldevice.lnurl(req)}}
    else:
        lnurldevice = await update_lnurldevice(data, lnurldevice_id=lnurldevice_id)
        return {**lnurldevice.dict(), **{"lnurl": lnurldevice.lnurl(req)}}


@lnurldevice_ext.get("/api/v1/lnurlpos")
async def api_lnurldevices_retrieve(
    req: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    try:
        return [
            {**lnurldevice.dict(), **{"lnurl": lnurldevice.lnurl(req)}}
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


@lnurldevice_ext.get("/api/v1/lnurlpos/{lnurldevice_id}")
async def api_lnurldevice_retrieve(
    req: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    lnurldevice_id: str = Query(None),
):
    lnurldevice = await get_lnurldevice(lnurldevice_id)
    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurldevice does not exist"
        )
    if not lnurldevice.lnurl_toggle:
        return {**lnurldevice.dict()}
    return {**lnurldevice.dict(), **{"lnurl": lnurldevice.lnurl(req)}}


@lnurldevice_ext.delete("/api/v1/lnurlpos/{lnurldevice_id}")
async def api_lnurldevice_delete(
    wallet: WalletTypeInfo = Depends(require_admin_key),
    lnurldevice_id: str = Query(None),
):
    lnurldevice = await get_lnurldevice(lnurldevice_id)

    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet link does not exist."
        )

    await delete_lnurldevice(lnurldevice_id)

    return "", HTTPStatus.NO_CONTENT
