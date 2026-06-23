import asyncio
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from loguru import logger

from lnbits.decorators import optional_user_id
from lnbits.settings import settings
from lnbits.utils.electrum import (
    AddressResponse,
    BlockHeader,
    BlockInfo,
    ElectrumClient,
    ElectrumError,
    FeeResponse,
    HistoryEntry,
    Transaction,
    parse_block_header,
    parse_raw_tx,
    scripthash_from_address,
    scripthash_from_scriptpubkey,
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
    user_id: str | None = Depends(optional_user_id),
) -> None:
    _check_enabled()
    if not settings.lnbits_blockexplorer_public_api and not user_id:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Authentication required.",
        )


def _client() -> ElectrumClient:
    return ElectrumClient(settings.lnbits_blockexplorer_electrum_url)


def _watch_scripthash(tx: Transaction) -> str | None:
    """Return scripthash of first spendable output to watch for tx confirmation."""
    for out in tx.vout:
        if out.scriptPubKey.type != "nulldata":
            return scripthash_from_scriptpubkey(bytes.fromhex(out.scriptPubKey.hex))
    return None


async def _tx_status(
    c: ElectrumClient, txid: str, scripthash: str | None
) -> dict[str, Any]:
    if scripthash:
        history: list[HistoryEntry] = await c.get_history(scripthash)
        for entry in history:
            if entry.tx_hash == txid:
                return {
                    "txid": txid,
                    "confirmed": entry.height > 0,
                    "height": entry.height if entry.height > 0 else None,
                    "fee": entry.fee,
                }
    return {"txid": txid, "confirmed": False, "height": None, "fee": None}


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


@blockexplorer_router.get("/address/{address}", dependencies=[Depends(_check_api_access)])
async def api_address(address: str) -> AddressResponse:
    try:
        scripthash = scripthash_from_address(address)
    except ValueError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    try:
        async with _client() as c:
            balance, history = await asyncio.gather(
                c.get_balance(scripthash),
                c.get_history(scripthash),
            )
        return AddressResponse(balance=balance, history=history)
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


@blockexplorer_router.websocket("/ws/address/{address}")
async def ws_address(websocket: WebSocket, address: str) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    try:
        scripthash = scripthash_from_address(address)
    except ValueError as e:
        await websocket.close(code=1008, reason=str(e))
        return
    await websocket.accept()
    try:
        async with _client() as c:
            await c.subscribe_scripthash(scripthash)
            balance, history = await asyncio.gather(
                c.get_balance(scripthash), c.get_history(scripthash)
            )
            resp = AddressResponse(balance=balance, history=history)
            await websocket.send_json(resp.dict())

            async def on_address_change(params: list[Any]) -> None:
                try:
                    bal, hist = await asyncio.gather(
                        c.get_balance(scripthash), c.get_history(scripthash)
                    )
                    await websocket.send_json(
                        AddressResponse(balance=bal, history=hist).dict()
                    )
                except Exception as e:
                    logger.debug(f"ws_address send error: {e}")

            c.on("blockchain.scripthash.subscribe", on_address_change)
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
    except Exception as e:
        logger.debug(f"ws_address error: {e}")


@blockexplorer_router.websocket("/ws/tx/{txid}")
async def ws_tx(websocket: WebSocket, txid: str) -> None:
    if not settings.lnbits_blockexplorer_enabled:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        async with _client() as c:
            try:
                raw = await c.get_transaction(txid)
            except ElectrumError as e:
                await websocket.send_json({"error": str(e)})
                return
            tx = parse_raw_tx(raw)
            watch = _watch_scripthash(tx)
            await websocket.send_json(await _tx_status(c, txid, watch))
            if watch:
                await c.subscribe_scripthash(watch)

                async def on_tx_change(params: list[Any]) -> None:
                    try:
                        await websocket.send_json(await _tx_status(c, txid, watch))
                    except Exception as e:
                        logger.debug(f"ws_tx send error: {e}")

                c.on("blockchain.scripthash.subscribe", on_tx_change)
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
    except Exception as e:
        logger.debug(f"ws_tx error: {e}")
