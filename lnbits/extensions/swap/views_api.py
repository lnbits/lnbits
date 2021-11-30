from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import Request
from fastapi.params import Depends, Query
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.swap.models import CreateRecurrent, CreateSwapOut

from . import swap_ext
from .crud import (
    create_recurrent,
    create_swapout,
    get_recurrents,
    get_swapouts,
    unique_recurrent_swapout,
    update_recurrent,
)
from .etleneum import create_queue_pay


# SWAP OUT
@swap_ext.get("/api/v1/out")
async def api_swap_outs(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [swap.dict() for swap in await get_swapouts(wallet_ids)]

@swap_ext.post("/api/v1/out")
async def api_swapout_create(
    data: CreateSwapOut,
    wallet: WalletTypeInfo = Depends(require_admin_key)
):
                
    swap_out = await create_swapout(data)
    return swap_out.dict()


## RECURRENT

@swap_ext.get("/api/v1/recurrent")
async def api_swap_outs(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [rec.dict() for rec in await get_recurrents(wallet_ids)]

@swap_ext.post("/api/v1/recurrent")
@swap_ext.put("/api/v1/recurrent/{swap_id}")
async def api_swapout_update_recurrent(
    data: CreateRecurrent,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    swap_id = None,
):
    if not swap_id:
        ## CHECK IF THERE'S ALREADY A RECURRENT SWAP
        ## ONLY ONE PER WALLET
        is_unique = await unique_recurrent_swapout(data.wallet)
        if is_unique > 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="This wallet already has a recurrent swap!"
            )
        recurrent = await create_recurrent(data=data)
        print("REC", recurrent)
        return recurrent.dict()
    else:
        recurrent = await update_recurrent(swap_id=swap_id, data=data)
        return recurrent.dict()
    