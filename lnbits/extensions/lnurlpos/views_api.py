import hashlib
from fastapi import FastAPI, Request
from fastapi.params import Depends
from http import HTTPStatus
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from fastapi.params import Depends
from fastapi.param_functions import Query
from lnbits.decorators import check_user_exists, WalletTypeInfo, get_key_type
from lnbits.core.crud import get_user
from lnbits.core.models import User, Payment
from . import lnurlpos_ext

from lnbits.extensions.lnurlpos import lnurlpos_ext
from .crud import (
    create_lnurlpos,
    update_lnurlpos,
    get_lnurlpos,
    get_lnurlposs,
    delete_lnurlpos,
)
from lnbits.utils.exchange_rates import currencies
from .models import createLnurlpos


@lnurlpos_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return list(currencies.keys())


#######################lnurlpos##########################


@lnurlpos_ext.post("/api/v1/lnurlpos")
@lnurlpos_ext.put("/api/v1/lnurlpos/{lnurlpos_id}")
async def api_lnurlpos_create_or_update(
    request: Request,
    data: createLnurlpos,
    wallet: WalletTypeInfo = Depends(get_key_type),
    lnurlpos_id: str = Query(None),
):
    if not lnurlpos_id:
        lnurlpos = await create_lnurlpos(data)
        print(lnurlpos.dict())
        return lnurlpos.dict()
    else:
        lnurlpos = await update_lnurlpos(data, lnurlpos_id=lnurlpos_id)
        return lnurlpos.dict()


@lnurlpos_ext.get("/api/v1/lnurlpos")
async def api_lnurlposs_retrieve(
    request: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    try:
        return [{**lnurlpos.dict()} for lnurlpos in await get_lnurlposs(wallet_ids)]
    except:
        return ""


@lnurlpos_ext.get("/api/v1/lnurlpos/{lnurlpos_id}")
async def api_lnurlpos_retrieve(
    request: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    lnurlpos_id: str = Query(None),
):
    lnurlpos = await get_lnurlpos(lnurlpos_id)
    if not lnurlpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurlpos does not exist"
        )
    if not lnurlpos.lnurl_toggle:
        return {**lnurlpos.dict()}
    return {**lnurlpos.dict(), **{"lnurl": lnurlpos.lnurl(request=request)}}


@lnurlpos_ext.delete("/api/v1/lnurlpos/{lnurlpos_id}")
async def api_lnurlpos_delete(
    request: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    lnurlpos_id: str = Query(None),
):
    lnurlpos = await get_lnurlpos(lnurlpos_id)

    if not lnurlpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet link does not exist."
        )

    await delete_lnurlpos(lnurlpos_id)

    return "", HTTPStatus.NO_CONTENT
