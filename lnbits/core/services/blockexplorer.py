import asyncio

from lnbits.settings import settings
from lnbits.task_manager import OnchainAddressEvent
from lnbits.utils.electrum import (
    UTXO,
    AddressResponse,
    Balance,
    BlockHeader,
    BlockInfo,
    ElectrumClient,
    FeeResponse,
    Transaction,
    network_from_name,
    parse_block_header,
    parse_raw_tx,
    scripthash_from_address,
)


def _client() -> ElectrumClient:
    return ElectrumClient(
        settings.lnbits_blockexplorer_electrum_url,
        network=network_from_name(settings.lnbits_blockexplorer_network),
    )


async def fetch_recent_blocks(count: int = 5) -> list[BlockInfo]:
    async with _client() as c:
        tip = await c.get_tip()
        start = max(0, tip.height - count + 1)
        headers = await c.get_block_headers(start, tip.height - start + 1)
    raw = bytes.fromhex(headers.hex)
    blocks = [
        parse_block_header(raw[i * 80 : (i + 1) * 80].hex(), start + i)
        for i in range(headers.count)
    ]
    return list(reversed(blocks))


async def fetch_tip() -> BlockHeader:
    async with _client() as c:
        return await c.get_tip()


async def fetch_fee_estimates() -> FeeResponse:
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


async def fetch_transaction(txid: str) -> Transaction:
    async with _client() as c:
        raw_hex = await c.get_transaction(txid)
    return parse_raw_tx(raw_hex, network=c.network)


async def fetch_onchain_balance(onchain_address: str) -> AddressResponse:
    scripthash = scripthash_from_address(onchain_address)
    async with _client() as client:
        balance_res, history_res = await asyncio.gather(
            client.get_balance(scripthash),
            client.get_history(scripthash),
            return_exceptions=True,
        )
    if isinstance(balance_res, BaseException):
        raise balance_res
    history = [] if isinstance(history_res, BaseException) else history_res
    history_error = str(history_res) if isinstance(history_res, BaseException) else None
    return AddressResponse(
        balance=balance_res, history=history, history_error=history_error
    )


async def fetch_utxos(onchain_address: str) -> list[UTXO]:
    scripthash = scripthash_from_address(onchain_address)
    async with _client() as client:
        return await client.listunspent(scripthash)


def address_event_to_response(event: OnchainAddressEvent) -> AddressResponse:
    return AddressResponse(
        balance=Balance(confirmed=event.confirmed, unconfirmed=event.unconfirmed),
        history=event.history,
        history_error=event.history_error,
    )
