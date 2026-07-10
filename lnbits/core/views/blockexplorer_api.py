import asyncio
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from pydantic.types import UUID4

from lnbits.core.services.blockexplorer import (
    address_event_to_response,
    fetch_fee_estimates,
    fetch_onchain_balance,
    fetch_recent_blocks,
    fetch_tip,
    fetch_transaction,
)
from lnbits.decorators import check_access_token, check_user_exists
from lnbits.settings import settings
from lnbits.task_manager import (
    OnchainAddressEvent,
    OnchainTxEvent,
    relay_ws_queue,
    task_manager,
)
from lnbits.utils.electrum import (
    AddressResponse,
    BlockHeader,
    BlockInfo,
    ElectrumError,
    FeeResponse,
    Transaction,
    scripthash_from_address,
)

blockexplorer_router = APIRouter(
    tags=["Block Explorer"],
    prefix="/blockexplorer/api/v1",
)


def _check_enabled() -> None:
    if not settings.lnbits_blockexplorer_enabled:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Block explorer is not enabled.",
        )


async def _check_api_access(
    r: Request,
    access_token: Annotated[str | None, Depends(check_access_token)],
    usr: UUID4 | None = None,
) -> None:
    _check_enabled()
    if not settings.lnbits_blockexplorer_public_api:
        await check_user_exists(r, access_token, usr)


# ---- REST ----


@blockexplorer_router.get("/blocks", dependencies=[Depends(_check_api_access)])
async def api_blocks() -> list[BlockInfo]:
    try:
        return await fetch_recent_blocks()
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/tip", dependencies=[Depends(_check_api_access)])
async def api_tip() -> BlockHeader:
    try:
        return await fetch_tip()
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/fees", dependencies=[Depends(_check_api_access)])
async def api_fees() -> FeeResponse:
    try:
        return await fetch_fee_estimates()
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/tx/{txid}", dependencies=[Depends(_check_api_access)])
async def api_tx(txid: str) -> Transaction:
    try:
        return await fetch_transaction(txid)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get(
    "/address/{address}", dependencies=[Depends(_check_api_access)]
)
async def api_address(address: str) -> AddressResponse:
    try:
        scripthash_from_address(address)
    except ValueError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    try:
        return await fetch_onchain_balance(address)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


# ---- WebSocket ----


@blockexplorer_router.websocket("/ws/blocks")
async def ws_blocks(websocket: WebSocket) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    queue: asyncio.Queue[BlockInfo] = asyncio.Queue()
    task_manager.register_ws_block_queue(queue)
    try:
        await relay_ws_queue(websocket, queue)
    finally:
        task_manager.unregister_ws_block_queue(queue)


@blockexplorer_router.websocket("/ws/address/{address}")
async def ws_address(websocket: WebSocket, address: str) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    queue: asyncio.Queue[OnchainAddressEvent] = asyncio.Queue()
    try:
        task_manager.register_ws_address_queue(address, queue)
    except ValueError as e:
        await websocket.close(code=1008, reason=str(e))
        return
    try:
        await relay_ws_queue(websocket, queue, serialize=address_event_to_response)
    finally:
        task_manager.unregister_ws_address_queue(address, queue)


@blockexplorer_router.websocket("/ws/tx/{txid}")
async def ws_tx(websocket: WebSocket, txid: str) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    queue: asyncio.Queue[OnchainTxEvent] = asyncio.Queue()
    task_manager.register_ws_tx_queue(txid, queue)
    try:
        await relay_ws_queue(websocket, queue, stop_after=lambda e: e.confirmed)
    finally:
        task_manager.unregister_ws_tx_queue(txid, queue)
