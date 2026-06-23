import asyncio
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from lnbits.settings import settings
from lnbits.utils.electrum import (
    AddressResponse,
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


def _client() -> ElectrumClient:
    return ElectrumClient(settings.lnbits_blockexplorer_electrum_url)


@blockexplorer_router.get("/blocks")
async def api_blocks() -> list[BlockInfo]:
    _check_enabled()
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


@blockexplorer_router.get("/tip")
async def api_tip() -> BlockHeader:
    _check_enabled()
    try:
        async with _client() as c:
            return await c.get_tip()
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/fees")
async def api_fees() -> FeeResponse:
    _check_enabled()
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


@blockexplorer_router.get("/tx/{txid}")
async def api_tx(txid: str) -> Transaction:
    _check_enabled()
    try:
        async with _client() as c:
            raw_hex = await c.get_transaction(txid)
        return parse_raw_tx(raw_hex)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e)) from e


@blockexplorer_router.get("/address/{address}")
async def api_address(address: str) -> AddressResponse:
    _check_enabled()
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
