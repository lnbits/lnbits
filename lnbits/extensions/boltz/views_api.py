from http import HTTPStatus
from typing import List

from fastapi import BackgroundTasks, Depends, Query, status
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import settings

from . import boltz_ext
from .crud import (
    create_auto_reverse_submarine_swap,
    create_reverse_submarine_swap,
    create_submarine_swap,
    get_auto_reverse_submarine_swaps,
    get_pending_reverse_submarine_swaps,
    get_pending_submarine_swaps,
    get_reverse_submarine_swap,
    get_reverse_submarine_swaps,
    get_submarine_swap,
    get_submarine_swaps,
    update_swap_status,
)
from .models import (
    AutoReverseSubmarineSwap,
    CreateAutoReverseSubmarineSwap,
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
    ReverseSubmarineSwap,
    SubmarineSwap,
)
from .utils import check_balance, create_boltz_client


@boltz_ext.get(
    "/api/v1/swap/mempool",
    name=f"boltz.get /swap/mempool",
    summary="get a the mempool url",
    description="""
        This endpoint gets the URL from mempool.space
    """,
    response_description="mempool.space url",
    response_model=str,
)
async def api_mempool_url():
    return settings.boltz_mempool_space_url


# NORMAL SWAP
@boltz_ext.get(
    "/api/v1/swap",
    name=f"boltz.get /swap",
    summary="get a list of swaps a swap",
    description="""
        This endpoint gets a list of normal swaps.
    """,
    response_description="list of normal swaps",
    dependencies=[Depends(get_key_type)],
    response_model=List[SubmarineSwap],
)
async def api_submarineswap(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    # client = create_boltz_client()
    # for swap in await get_pending_submarine_swaps(wallet_ids):
    #     try:
    #         swap_status = client.swap_status(swap.boltz_id)
    #     # if swap_status.hit_timeout:
    #     #     if not swap_status.has_lockup:
    #     #         logger.warning(
    #     #             f"Boltz - swap: {swap.id} hit timeout, but no lockup tx..."
    #     #         )
    #     #         await update_swap_status(swap.id, "timeout")

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
    response_model=SubmarineSwap,
    responses={
        400: {"description": "when swap_id is missing"},
        404: {"description": "when swap is not found"},
        405: {"description": "when swap is not pending"},
        500: {
            "description": "when something goes wrong creating the refund onchain tx"
        },
    },
)
async def api_submarineswap_refund(swap_id: str):
    if not swap_id:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="swap_id missing"
        )
    swap = await get_submarine_swap(swap_id)
    if not swap:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="swap does not exist."
        )
    if swap.status != "pending":
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="swap is not pending."
        )

    client = create_boltz_client()
    await client.refund_swap(
        privkey_wif=swap.refund_privkey,
        lockup_address=swap.address,
        receive_address=swap.refund_address,
        redeem_script_hex=swap.redeem_script,
        timeout_block_height=swap.timeout_block_height,
    )

    await update_swap_status(swap.id, "refunded")
    return swap


@boltz_ext.post(
    "/api/v1/swap",
    status_code=status.HTTP_201_CREATED,
    name=f"boltz.post /swap",
    summary="create a submarine swap",
    description="""
        This endpoint creates a submarine swap
    """,
    response_description="create swap",
    response_model=SubmarineSwap,
    dependencies=[Depends(require_admin_key)],
    responses={
        405: {"description": "not allowed method, insufficient balance"},
        500: {"description": "boltz error"},
    },
)
async def api_submarineswap_create(data: CreateSubmarineSwap):
    client = create_boltz_client()
    swap_id = urlsafe_short_hash()
    payment_hash, payment_request = await create_invoice(
        wallet_id=data.wallet,
        amount=data.amount,
        memo=f"swap of {data.amount} sats on boltz.exchange",
        extra={"tag": "boltz", "swap_id": swap_id},
    )
    refund_privkey_wif, swap = client.create_swap(payment_request)
    new_swap = await create_submarine_swap(
        data, swap, swap_id, refund_privkey_wif, payment_hash
    )
    return new_swap.dict() if new_swap else None


# REVERSE SWAP
@boltz_ext.get(
    "/api/v1/swap/reverse",
    name=f"boltz.get /swap/reverse",
    summary="get a list of reverse swaps",
    description="""
        This endpoint gets a list of reverse swaps.
    """,
    response_description="list of reverse swaps",
    dependencies=[Depends(get_key_type)],
    response_model=List[ReverseSubmarineSwap],
)
async def api_reverse_submarineswap(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []
    return [swap.dict() for swap in await get_reverse_submarine_swaps(wallet_ids)]


@boltz_ext.post(
    "/api/v1/swap/reverse",
    status_code=status.HTTP_201_CREATED,
    name=f"boltz.post /swap/reverse",
    summary="create a reverse submarine swap",
    description="""
        This endpoint creates a reverse submarine swap
    """,
    response_description="create reverse swap",
    response_model=ReverseSubmarineSwap,
    dependencies=[Depends(require_admin_key)],
    responses={
        405: {"description": "not allowed method, insufficient balance"},
        500: {"description": "boltz error"},
    },
)
async def api_reverse_submarineswap_create(
    data: CreateReverseSubmarineSwap, bg: BackgroundTasks
):

    if not await check_balance(data):
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="Insufficient balance."
        )

    client = create_boltz_client()
    claim_privkey_wif, preimage_hex, swap = client.create_reverse_swap(
        amount=data.amount
    )

    bg.add_task(
        client.claim_reverse_swap,
        privkey_wif=claim_privkey_wif,
        preimage_hex=preimage_hex,
        lockup_address=swap.lockupAddress,
        receive_address=data.onchain_address,
        redeem_script_hex=swap.redeemScript,
    )

    swap_id = urlsafe_short_hash()
    bg.add_task(
        pay_invoice,
        wallet_id=data.wallet,
        payment_request=swap.invoice,
        description=f"reverse swap for {swap.onchainAmount} sats on boltz.exchange",
        extra={"tag": "boltz", "swap_id": swap_id, "reverse": True},
    )

    new_swap = await create_reverse_submarine_swap(
        swap, data, swap_id, claim_privkey_wif, preimage_hex
    )
    return new_swap.dict() if new_swap else None


@boltz_ext.get(
    "/api/v1/swap/reverse/auto",
    name=f"boltz.get /swap/reverse/auto",
    summary="get a list of auto reverse swaps",
    description="""
        This endpoint gets a list of auto reverse swaps.
    """,
    response_description="list of auto reverse swaps",
    dependencies=[Depends(get_key_type)],
    response_model=List[AutoReverseSubmarineSwap],
)
async def api_auto_reverse_submarineswap(
    g: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []
    return [swap.dict() for swap in await get_auto_reverse_submarine_swaps(wallet_ids)]


@boltz_ext.post(
    "/api/v1/swap/reverse/auto",
    status_code=status.HTTP_201_CREATED,
    name=f"boltz.post /swap/reverse/auto",
    summary="create a auto reverse submarine swap",
    description="""
        This endpoint creates a auto reverse submarine swap
    """,
    response_description="create auto reverse swap",
    response_model=AutoReverseSubmarineSwap,
    dependencies=[Depends(require_admin_key)],
)
async def api_auto_reverse_submarineswap_create(data: CreateAutoReverseSubmarineSwap):
    swap = await create_auto_reverse_submarine_swap(data)
    return swap.dict() if swap else None


@boltz_ext.post(
    "/api/v1/swap/status",
    name=f"boltz.swap_status",
    summary="shows the status of a swap",
    description="""
        This endpoint attempts to get the status of the swap.
    """,
    response_description="status of swap json",
    dependencies=[Depends(require_admin_key)],
    responses={
        404: {"description": "when swap_id is not found"},
    },
)
async def api_swap_status(swap_id: str):
    swap = await get_submarine_swap(swap_id) or await get_reverse_submarine_swap(
        swap_id
    )
    if not swap:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="swap does not exist."
        )

    client = create_boltz_client()
    status = client.swap_status(swap.boltz_id)
    return status


@boltz_ext.post(
    "/api/v1/swap/check",
    name=f"boltz.swap_check",
    summary="list all pending swaps",
    description="""
        This endpoint gives you 2 lists of pending swaps and reverse swaps.
    """,
    response_description="list of pending swaps",
)
async def api_check_swaps(
    g: WalletTypeInfo = Depends(require_admin_key),
    all_wallets: bool = Query(False),
) -> List:
    wallet_ids = [g.wallet.id]
    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []
    status = []
    client = create_boltz_client()
    for swap in await get_pending_submarine_swaps(wallet_ids):
        status.append(client.swap_status(swap.boltz_id))
    for reverseswap in await get_pending_reverse_submarine_swaps(wallet_ids):
        status.append(client.swap_status(reverseswap.boltz_id))
    return status


@boltz_ext.get(
    "/api/v1/swap/boltz",
    name=f"boltz.get /swap/boltz",
    summary="get a boltz configuration",
    description="""
        This endpoint gets configuration for boltz. (limits, fees...)
    """,
    response_description="dict of boltz config",
    response_model=dict,
)
async def api_boltz_config():
    client = create_boltz_client()
    return {"minimal": client.limit_minimal, "maximal": client.limit_maximal}
