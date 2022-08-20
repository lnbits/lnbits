from datetime import datetime
from http import HTTPStatus

from fastapi.param_functions import Body
from fastapi.params import Depends, Query
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.crud import get_user
from lnbits.core.services import perform_lnurlauth, redeem_lnurl_withdraw
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from .models import (
    SubmarineSwap,
    ReverseSubmarineSwap,
    CreateSubmarineSwap,
    CreateReverseSubmarineSwap,
)

from . import boltz_ext

from .boltz import (
    create_swap,
    create_reverse_swap,
    create_refund_tx,
    get_boltz_pairs,
    get_swap_status,
    MEMPOOL_SPACE_URL,
)

from .crud import (
    update_swap_status,
    create_submarine_swap,
    get_submarine_swaps,
    get_submarine_swap,
    create_reverse_submarine_swap,
    get_reverse_submarine_swaps,
    get_reverse_submarine_swap,
)


@boltz_ext.get("/api/v1/swap/mempool")
async def api_mempool_url():
    return MEMPOOL_SPACE_URL


# NORMAL SWAP
@boltz_ext.get("/api/v1/swap")
async def api_submarineswap(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    return [swap.dict() for swap in await get_submarine_swaps(wallet_ids)]


@boltz_ext.get("/api/v1/swap/refund/{submarineSwapId}")
async def api_submarineswap_refund(submarineSwapId: str):
    swap = await get_submarine_swap(submarineSwapId)
    if swap == None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="submarine swap does not exist."
        )
    if swap.status == "refunded":
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="swap already refunded."
        )
    await create_refund_tx(swap)
    await update_swap_status(swap, "refunded")
    return swap


@boltz_ext.post("/api/v1/swap")
async def api_submarineswap_create(
    data: CreateSubmarineSwap, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    data = await create_swap(data)
    swap = await create_submarine_swap(data)
    return swap.dict()


# REVERSE SWAP
@boltz_ext.get("/api/v1/swap/reverse")
async def api_reverse_submarineswap(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    return [swap.dict() for swap in await get_reverse_submarine_swaps(wallet_ids)]


@boltz_ext.post("/api/v1/swap/reverse")
async def api_reverse_submarineswap_create(
    data: CreateReverseSubmarineSwap,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    data = await create_reverse_swap(data)
    swap = await create_reverse_submarine_swap(data)
    return swap.dict()


# STATUS
@boltz_ext.get("/api/v1/swap/status/{swap_id}")
async def api_submarineswap_status(swap_id: str):
    swap = await get_submarine_swap(swap_id)
    if swap == None:
        swap = await get_reverse_submarine_swap(swap_id)
        if swap == None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="swap does not exist."
            )
    return get_swap_status(swap)


@boltz_ext.get("/api/v1/swap/check")
async def api_check_swaps(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    status = []
    for swap in await get_submarine_swaps(wallet_ids):
        if swap.status == "pending":
            status.append(get_swap_status(swap))
    return status


@boltz_ext.get("/api/v1/swap/boltz")
async def api_boltz_config():
    res = get_boltz_pairs()
    return res["pairs"]["BTC/BTC"]
