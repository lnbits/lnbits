import asyncio
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from lnbits.settings import settings
from lnbits.utils.electrum import (
    AddressResponse,
    BlockHeader,
    ElectrumClient,
    ElectrumError,
    FeeResponse,
    Transaction,
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


@blockexplorer_router.get("/tip")
async def api_tip() -> BlockHeader:
    _check_enabled()
    try:
        async with _client() as c:
            return await c.get_tip()
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e))


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
            for blocks, fee in zip([1, 3, 6, 144], estimates_raw)
            if fee >= 0
        }
        return FeeResponse(estimates=estimates, histogram=histogram)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e))


@blockexplorer_router.get("/tx/{txid}")
async def api_tx(txid: str) -> Transaction:
    _check_enabled()
    try:
        async with _client() as c:
            raw_hex = await c.get_transaction(txid, verbose=False)
        return parse_raw_tx(raw_hex)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e))


@blockexplorer_router.get("/address/{address}")
async def api_address(address: str) -> AddressResponse:
    _check_enabled()
    try:
        scripthash = scripthash_from_address(address)
    except ValueError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail=str(e))
    try:
        async with _client() as c:
            balance, history = await asyncio.gather(
                c.get_balance(scripthash),
                c.get_history(scripthash),
            )
        return AddressResponse(balance=balance, history=history)
    except ElectrumError as e:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail=str(e))
