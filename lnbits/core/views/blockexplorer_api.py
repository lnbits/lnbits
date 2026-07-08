import asyncio
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from loguru import logger
from pydantic.types import UUID4

from lnbits.decorators import check_access_token, check_user_exists
from lnbits.settings import settings
from lnbits.task_manager import OnchainAddressEvent, OnchainTxEvent, task_manager
from lnbits.utils.electrum import (
    AddressResponse,
    Balance,
    BlockHeader,
    BlockInfo,
    ElectrumClient,
    ElectrumError,
    FeeResponse,
    Transaction,
    parse_block_header,
    parse_raw_tx,
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


def _client() -> ElectrumClient:
    return ElectrumClient(settings.lnbits_blockexplorer_electrum_url)


# ---- REST ----


@blockexplorer_router.get("/blocks", dependencies=[Depends(_check_api_access)])
async def api_blocks() -> list[BlockInfo]:
    try:
        async with _client() as c:
            tip = await c.get_tip()
            start = max(0, tip.height - 4)
            headers = await c.get_block_headers(start, tip.height - start + 1)
        raw = bytes.fromhex(headers.hex)
        blocks = [
            parse_block_header(raw[i * 80 : (i + 1) * 80].hex(), start + i)
            for i in range(headers.count)
        ]
        return list(reversed(blocks))
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/tip", dependencies=[Depends(_check_api_access)])
async def api_tip() -> BlockHeader:
    try:
        async with _client() as c:
            return await c.get_tip()
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/fees", dependencies=[Depends(_check_api_access)])
async def api_fees() -> FeeResponse:
    try:
        async with _client() as c:
            estimates_raw = await asyncio.gather(
                c.estimate_fee(1),
                c.estimate_fee(3),
                c.estimate_fee(6),
                c.estimate_fee(144),
            )
            histogram = await c.fee_histogram()
        estimates = {
            str(blocks): fee
            for blocks, fee in zip([1, 3, 6, 144], estimates_raw, strict=False)
            if fee >= 0
        }
        return FeeResponse(estimates=estimates, histogram=histogram)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/tx/{txid}", dependencies=[Depends(_check_api_access)])
async def api_tx(txid: str) -> Transaction:
    try:
        async with _client() as c:
            raw_hex = await c.get_transaction(txid)
        return parse_raw_tx(raw_hex)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get(
    "/address/{address}", dependencies=[Depends(_check_api_access)]
)
async def api_address(address: str) -> AddressResponse:
    try:
        scripthash = scripthash_from_address(address)
    except ValueError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    try:
        async with _client() as c:
            balance_res, history_res = await asyncio.gather(
                c.get_balance(scripthash),
                c.get_history(scripthash),
                return_exceptions=True,
            )
        if isinstance(balance_res, BaseException):
            raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(balance_res))
        history = [] if isinstance(history_res, BaseException) else history_res
        history_error = (
            str(history_res) if isinstance(history_res, BaseException) else None
        )
        return AddressResponse(
            balance=balance_res, history=history, history_error=history_error
        )
    except HTTPException:
        raise
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


# ---- WebSocket ----


@blockexplorer_router.websocket("/ws/blocks")
async def ws_blocks(websocket: WebSocket) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        async with _client() as c:
            tip = await c.subscribe_headers()
            await websocket.send_json(parse_block_header(tip.hex, tip.height).dict())

            async def on_header(params: list[Any]) -> None:
                h = params[0]
                try:
                    await websocket.send_json(
                        parse_block_header(h["hex"], h["height"]).dict()
                    )
                except Exception as e:
                    logger.debug(f"ws_blocks send error: {e}")

            c.on("blockchain.headers.subscribe", on_header)
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
    except Exception as e:
        logger.debug(f"ws_blocks error: {e}")


def _address_event_to_response(event: OnchainAddressEvent) -> AddressResponse:
    return AddressResponse(
        balance=Balance(confirmed=event.confirmed, unconfirmed=event.unconfirmed),
        history=event.history,
        history_error=event.history_error,
    )


@blockexplorer_router.websocket("/ws/address/{address}")
async def ws_address(websocket: WebSocket, address: str) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    try:
        scripthash_from_address(address)  # validate
    except ValueError as e:
        await websocket.close(code=1008, reason=str(e))
        return
    await websocket.accept()

    queue: asyncio.Queue[OnchainAddressEvent] = asyncio.Queue()
    task_manager.register_ws_address_queue(address, queue)
    try:
        await _ws_address_loop(websocket, address, queue)
    finally:
        task_manager.unregister_ws_address_queue(address, queue)


async def _ws_address_loop(
    websocket: WebSocket,
    address: str,
    queue: asyncio.Queue[OnchainAddressEvent],
) -> None:
    try:
        while True:
            recv_task = asyncio.create_task(websocket.receive())
            event_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                [recv_task, event_task], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            if recv_task in done:
                if recv_task.result().get("type") == "websocket.disconnect":
                    break
            if event_task in done:
                try:
                    await websocket.send_json(
                        _address_event_to_response(event_task.result()).dict()
                    )
                except Exception as exc:
                    logger.debug(f"ws_address send error: {exc}")
                    break
    except Exception as exc:
        logger.debug(f"ws_address error: {exc}")


@blockexplorer_router.websocket("/ws/tx/{txid}")
async def ws_tx(websocket: WebSocket, txid: str) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    queue: asyncio.Queue[OnchainTxEvent] = asyncio.Queue()
    task_manager.register_ws_tx_queue(txid, queue)
    try:
        await _ws_tx_loop(websocket, queue)
    finally:
        task_manager.unregister_ws_tx_queue(txid, queue)


async def _ws_tx_loop(
    websocket: WebSocket,
    queue: asyncio.Queue[OnchainTxEvent],
) -> None:
    try:
        while True:
            recv_task = asyncio.create_task(websocket.receive())
            event_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                [recv_task, event_task], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            if recv_task in done:
                if recv_task.result().get("type") == "websocket.disconnect":
                    break
            if event_task in done:
                event: OnchainTxEvent = event_task.result()
                try:
                    await websocket.send_json(event.dict())
                except Exception as exc:
                    logger.debug(f"ws_tx send error: {exc}")
                    break
                if event.confirmed:
                    break
    except Exception as exc:
        logger.debug(f"ws_tx error: {exc}")
