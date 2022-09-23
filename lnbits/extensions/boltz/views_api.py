from datetime import datetime
from http import HTTPStatus
from typing import List

import httpx
from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.param_functions import Body
from fastapi.params import Depends, Query
from loguru import logger
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.settings import BOLTZ_MEMPOOL_SPACE_URL

from . import boltz_ext
from .boltz import (
    create_refund_tx,
    create_reverse_swap,
    create_swap,
    get_boltz_pairs,
    get_swap_status,
)
from .crud import (
    create_reverse_submarine_swap,
    create_submarine_swap,
    get_pending_reverse_submarine_swaps,
    get_pending_submarine_swaps,
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
from .utils import check_balance


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
    return BOLTZ_MEMPOOL_SPACE_URL


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
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    for swap in await get_pending_submarine_swaps(wallet_ids):
        swap_status = get_swap_status(swap)
        if swap_status.hit_timeout:
            if not swap_status.has_lockup:
                logger.warning(
                    f"Boltz - swap: {swap.id} hit timeout, but no lockup tx..."
                )
                await update_swap_status(swap.id, "timeout")

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
async def api_submarineswap_refund(
    swap_id: str,
    g: WalletTypeInfo = Depends(require_admin_key),  # type: ignore
):
    if swap_id == None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="swap_id missing"
        )

    swap = await get_submarine_swap(swap_id)
    if swap == None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="swap does not exist."
        )

    if swap.status != "pending":
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="swap is not pending."
        )

    try:
        await create_refund_tx(swap)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Unreachable: {exc.request.url!r}.",
        )
    except Exception as exc:
        raise HTTPException(status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail=str(exc))

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
    responses={
        405: {"description": "not allowed method, insufficient balance"},
        500: {"description": "boltz error"},
    },
)
async def api_submarineswap_create(
    data: CreateSubmarineSwap,
    wallet: WalletTypeInfo = Depends(require_admin_key),  # type: ignore
):
    try:
        swap_data = await create_swap(data)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Unreachable: {exc.request.url!r}.",
        )
    except Exception as exc:
        raise HTTPException(status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.json()["error"]
        )
    swap = await create_submarine_swap(swap_data)
    return swap.dict()


# REVERSE SWAP
@boltz_ext.get(
    "/api/v1/swap/reverse",
    name=f"boltz.get /swap/reverse",
    summary="get a list of reverse swaps a swap",
    description="""
        This endpoint gets a list of reverse swaps.
    """,
    response_description="list of reverse swaps",
    dependencies=[Depends(get_key_type)],
    response_model=List[ReverseSubmarineSwap],
)
async def api_reverse_submarineswap(
    g: WalletTypeInfo = Depends(get_key_type),  # type:ignore
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
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
    responses={
        405: {"description": "not allowed method, insufficient balance"},
        500: {"description": "boltz error"},
    },
)
async def api_reverse_submarineswap_create(
    data: CreateReverseSubmarineSwap,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):

    if not await check_balance(data):
        raise HTTPException(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail="Insufficient balance."
        )

    try:
        swap_data, task = await create_reverse_swap(data)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Unreachable: {exc.request.url!r}.",
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.json()["error"]
        )
    except Exception as exc:
        raise HTTPException(status_code=HTTPStatus.METHOD_NOT_ALLOWED, detail=str(exc))

    swap = await create_reverse_submarine_swap(swap_data)
    return swap.dict()


@boltz_ext.post(
    "/api/v1/swap/status",
    name=f"boltz.swap_status",
    summary="shows the status of a swap",
    description="""
        This endpoint attempts to get the status of the swap.
    """,
    response_description="status of swap json",
    responses={
        404: {"description": "when swap_id is not found"},
    },
)
async def api_swap_status(
    swap_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)  # type: ignore
):
    swap = await get_submarine_swap(swap_id) or await get_reverse_submarine_swap(
        swap_id
    )
    if swap == None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="swap does not exist."
        )
    try:
        status = get_swap_status(swap)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Unreachable: {exc.request.url!r}.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
        )
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
    g: WalletTypeInfo = Depends(require_admin_key),  # type: ignore
    all_wallets: bool = Query(False),
):
    wallet_ids = [g.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    status = []
    try:
        for swap in await get_pending_submarine_swaps(wallet_ids):
            status.append(get_swap_status(swap))
        for reverseswap in await get_pending_reverse_submarine_swaps(wallet_ids):
            status.append(get_swap_status(reverseswap))
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Unreachable: {exc.request.url!r}.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
        )
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
    try:
        res = get_boltz_pairs()
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Unreachable: {exc.request.url!r}.",
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return res["pairs"]["BTC/BTC"]
