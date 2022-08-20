from datetime import datetime
from http import HTTPStatus

from fastapi.param_functions import Body
from fastapi.params import Depends, Query
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.crud import get_user
from lnbits.core.services import perform_lnurlauth, redeem_lnurl_withdraw
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import boltz_ext
from .boltz import (
    MEMPOOL_SPACE_URL,
    create_refund_tx, create_reverse_swap, create_swap, get_boltz_pairs,
    get_swap_status,
)
from .crud import (
    create_reverse_submarine_swap,
    create_submarine_swap,
    get_reverse_submarine_swap,
    get_reverse_submarine_swaps,
    get_submarine_swap,
    get_submarine_swaps,
    update_swap_status,
)
from .models import (
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
    ReverseSubmarineSwap,
    SubmarineSwap,
)


class SwapId(BaseModel):
    swap_id: str


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


@boltz_ext.post(
    "/api/v1/swap/refund",
    name=f"boltz.swap_refund",
    summary="refund of a swap",
    description="""
        This endpoint attempts to refund a normal swaps, creates onchain tx and sets swap status ro refunded.
    """,
    response_description="refunded swap with status set to refunded",
    dependencies=[Depends(require_admin_key)],
    response_model=str,
    responses={
        400: {"description": "when swap_id is missing"},
        404: {"description": "when swap is not found"},
        405: {"description": "when swap is already refunded"},
        500: {"description": "when something goes wrong creating the refund onchain tx"},
    },
)
async def api_submarineswap_refund(
    swap_id: int = Query(..., description="The ID of the swap"),
):
    if swap_id == None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="swap_id missing"
        )

    swap = await get_submarine_swap(q.swap_id)
    if swap == None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="submarine swap does not exist."
        )

    if swap.status == "refunded":
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="swap already refunded."
        )

    try:
        await create_refund_tx(swap)
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)
        )

    await update_swap_status(swap, "refunded")
    return swap


@boltz_ext.post("/api/v1/swap")
async def api_submarineswap_create(
    data: CreateSubmarineSwap, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        data = await create_swap(data)
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)
        )
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
    # check if we can pay the invoice before we create the actual swap on boltz
    amount_msat = data.amount * 1000
    fee_reserve_msat = fee_reserve(amount_msat)
    wallet = await get_wallet(data.wallet)
    assert wallet
    if wallet.balance_msat - fee_reserve_msat < amount_msat:
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="Insufficient balance."
        )

    try:
        data, task = await create_reverse_swap(data)
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)
        )

    swap = await create_reverse_submarine_swap(data)
    return swap.dict()


# STATUS
@boltz_ext.post(
    "/api/v1/swap/status",
    name=f"boltz.swap_status",
    summary="shows the status of a swap",
    description="""
        This endpoint attempts to get the status of the swap.
    """,
    response_description="status of swap json",
    dependencies=[Depends(require_admin_key)],
    response_model=str,
    responses={
        404: {"description": "when swap_id is not found"},
    },
)
async def api_submarineswap_status(
    swap_id: int = Query(..., description="The ID of the swap"),
):
    swap = await get_submarine_swap(swap_id)
    if swap == None:
        swap = await get_reverse_submarine_swap(swap_id)
        if swap == None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="swap does not exist."
            )
    return get_swap_status(swap)


@boltz_ext.post(
    "/api/v1/swap/check",
    name=f"boltz.swap_check",
    summary="list all pending swaps",
    description="""
        This endpoint gives you a list of pending swaps.
    """,
    response_description="list of pending swaps",
)
async def api_check_swaps(
    g: WalletTypeInfo = Depends(require_admin_key),
    all_wallets: bool = Query(False)
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
    try:
        res = get_boltz_pairs()
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)
        )

    return res["pairs"]["BTC/BTC"]
