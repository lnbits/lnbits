from http import HTTPStatus
import json
import httpx
import random
import os
from fastapi import Query
from fastapi.params import Depends
from lnurl import decode as decode_lnurl
from loguru import logger
from starlette.exceptions import HTTPException


from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from fastapi.templating import Jinja2Templates

from . import gerty_ext
from .crud import create_gerty, delete_gerty, get_gerty, get_gertys
from .models import Gerty

from lnbits.utils.exchange_rates import fiat_amount_as_satoshis
from ...settings import LNBITS_PATH


@gerty_ext.get("/api/v1/gerty", status_code=HTTPStatus.OK)
async def api_gertys(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [gerty.dict() for gerty in await get_gertys(wallet_ids)]


@gerty_ext.post("/api/v1/gerty", status_code=HTTPStatus.CREATED)
@gerty_ext.put("/api/v1/gerty/{gerty_id}", status_code=HTTPStatus.OK)
async def api_link_create_or_update(
    data: Gerty,
    wallet: WalletTypeInfo = Depends(get_key_type),
    gerty_id: str = Query(None),
):
    if gerty_id:
        gerty = await get_gerty(gerty_id)
        if not gerty:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Gerty does not exist"
            )

        if gerty.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Come on, seriously, this isn't your Gerty!",
            )

        data.wallet = wallet.wallet.id
        gerty = await update_gerty(gerty_id, **data.dict())
    else:
        gerty = await create_gerty(wallet_id=wallet.wallet.id, data=data)

    return {**gerty.dict()}

@gerty_ext.delete("/api/v1/gerty/{gerty_id}")
async def api_gerty_delete(
    gerty_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    gerty = await get_gerty(gerty_id)

    if not gerty:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Gerty does not exist."
        )

    if gerty.wallet != wallet.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your Gerty.")

    await delete_gerty(gerty_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


#######################

with open(os.path.join(LNBITS_PATH, 'extensions/gerty/static/satoshi.json')) as fd:
     satoshiQuotes = json.load(fd)

@gerty_ext.get("/api/v1/gerty/satoshiquote", status_code=HTTPStatus.OK)
async def api_gerty_satoshi():
    return satoshiQuotes[random.randint(0, 100)]
    
@gerty_ext.get("/api/v1/gerty/{gerty_id}")
async def api_gerty_json(
    gerty_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    gerty = await get_gerty(gerty_id)
    if not gerty:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Gerty does not exist."
        )
    if gerty.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Come on, seriously, this isn't your Gerty!",
        )
    gertyReturn = []
    if gerty.lnbits_wallets != "":
        gertyReturn.append(gerty.lnbitsWallets)
    
    if gerty.sats_quote:
        gertyReturn.append(await api_gerty_satoshi())

    if gerty.exchange != "":
        try:
            gertyReturn.append(await fiat_amount_as_satoshis(1, gerty.exchange))
        except:
            pass
    if gerty.onchain_sats:
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/v1/difficulty-adjustment")
            gertyReturn.append({"difficulty-adjustment": json.dumps(r)})
            r = await client.get(gerty.mempool_endpoint + "/api/v1/fees/mempool-blocks")
            gertyReturn.append({"mempool-blocks": json.dumps(r)})
            r = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/3d")
            gertyReturn.append({"3d": json.dumps(r)})

    if gerty.ln_sats:
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/v1/lightning/statistics/latest")
            gertyReturn.append({"latest": json.dumps(r)})

    return gertyReturn


