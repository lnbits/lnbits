import asyncio
import math
import re

import httpx
from embit.transaction import Transaction as EmbitTransaction
from starlette.concurrency import run_in_threadpool

from lnbits.core.models.onchain import ScanCheckpoint
from lnbits.core.models.wallets import OnchainConfig
from lnbits.settings import settings
from lnbits.task_manager import OnchainAddressEvent
from lnbits.utils.electrum import (
    UTXO,
    AddressResponse,
    Balance,
    BlockHeader,
    BlockInfo,
    BlockTransaction,
    BlockTransactions,
    ElectrumClient,
    FeeResponse,
    Transaction,
    network_from_name,
    parse_block_header,
    parse_raw_tx,
    scripthash_from_address,
)

TXID = re.compile(r"^[0-9a-f]{64}$")
NETWORKS = {"main": "Mainnet", "test": "Testnet", "test4": "Testnet4"}
_WALLET_TXID = re.compile(r"^[0-9a-f]{64}$")


class BlockExplorerWalletSession:
    """One explorer connection for complete wallet scans and payment operations."""

    def __init__(self) -> None:
        self.client = _client()
        self.transactions: dict[str, EmbitTransaction] = {}
        self.details: dict[str, dict] = {}
        self.blocks: dict[int, dict] = {}

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.client.__aexit__(*args)

    async def raw_transaction(self, txid: str) -> str:
        return await self.client.get_transaction(txid)

    async def checkpoint(self) -> ScanCheckpoint:
        tip = await self.client.get_tip()
        block = parse_block_header(tip.hex, tip.height)
        return ScanCheckpoint(height=tip.height, block_hash=block.hash)

    async def block_hash(self, height: int) -> str:
        # Bypass the session cache when checking for reorganisations.
        header = await self.client.get_block_header(height)
        if not isinstance(header, str):
            raise ValueError("Invalid block header")
        return parse_block_header(header, height).hash

    async def _transaction(self, txid: str) -> EmbitTransaction:
        if not _WALLET_TXID.fullmatch(txid):
            raise ValueError("Invalid transaction ID")
        if txid not in self.transactions:
            raw = await self.raw_transaction(txid)
            if len(raw) > 8_000_000:
                raise ValueError("Transaction too large")
            tx = await run_in_threadpool(EmbitTransaction.parse, bytes.fromhex(raw))
            if tx.txid().hex() != txid:
                raise ValueError("Transaction ID mismatch")
            if len(self.transactions) >= 10000:
                self.transactions.clear()
            self.transactions[txid] = tx
        return self.transactions[txid]

    def _outputs(self, tx: EmbitTransaction) -> list[dict]:
        outputs = []
        for output in tx.vout:
            try:
                address = output.script_pubkey.address(self.client.network)
            except ValueError:
                address = None
            outputs.append(
                {
                    "value": output.value,
                    "scriptpubkey": output.script_pubkey.data.hex(),
                    "scriptpubkey_address": address,
                }
            )
        return outputs

    async def _status(self, height: int) -> dict:
        if height <= 0:
            return {"confirmed": False}
        if height not in self.blocks:
            header = await self.client.get_block_header(height)
            if not isinstance(header, str):
                raise ValueError("Invalid block header")
            block = parse_block_header(header, height)
            self.blocks[height] = {
                "confirmed": True,
                "block_height": height,
                "block_time": block.timestamp,
                "block_hash": block.hash,
            }
        return self.blocks[height].copy()

    async def history(
        self,
        address: str,
        *,
        previous: list[dict] | None = None,
        checkpoint: ScanCheckpoint | None = None,
    ) -> list[dict]:
        history = await self.client.get_history(scripthash_from_address(address))
        if len(history) > 25000:
            raise ValueError("Explorer history limit reached")
        if len(self.details) >= 10000:
            self.details.clear()
        self.details.update({tx["txid"]: tx for tx in previous or []})
        transactions = []
        for entry in history:
            cached = self.details.get(entry.tx_hash)
            if cached is not None:
                status = cached["status"]
                if not (
                    checkpoint
                    and status["confirmed"]
                    and status["block_height"] == entry.height
                    and 0 < entry.height <= checkpoint.height
                ):
                    status = await self._status(entry.height)
                transactions.append({**cached, "status": status})
                self.details[entry.tx_hash] = transactions[-1]
                continue
            tx = await self._transaction(entry.tx_hash)
            vin = []
            for inp in tx.vin:
                coinbase = inp.txid == bytes(32) and inp.vout == 0xFFFFFFFF
                prevout = None
                if not coinbase:
                    parent = self.details.get(inp.txid.hex())
                    outputs = (
                        parent["vout"]
                        if parent is not None
                        else self._outputs(await self._transaction(inp.txid.hex()))
                    )
                    prevout = outputs[inp.vout]
                vin.append(
                    {
                        "txid": inp.txid.hex(),
                        "vout": inp.vout,
                        "prevout": prevout,
                        "is_coinbase": coinbase,
                        "sequence": inp.sequence,
                    }
                )
            vout = self._outputs(tx)
            fee = (
                0
                if any(i["is_coinbase"] for i in vin)
                else (
                    sum(i["prevout"]["value"] for i in vin)
                    - sum(o["value"] for o in vout)
                )
            )
            if fee < 0:
                raise ValueError("Invalid transaction fee")
            transactions.append(
                {
                    "txid": entry.tx_hash,
                    "vin": vin,
                    "vout": vout,
                    "fee": fee,
                    "status": await self._status(entry.height),
                }
            )
            self.details[entry.tx_hash] = transactions[-1]
        return transactions

    async def utxos(self, address: str) -> list[dict]:
        coins = await self.client.listunspent(scripthash_from_address(address))
        return [
            {
                "txid": coin.tx_hash,
                "vout": coin.tx_pos,
                "value": coin.value,
                "status": await self._status(coin.height),
            }
            for coin in coins
        ]

    async def fees(self) -> dict:
        rates = await asyncio.gather(
            *(self.client.estimate_fee(blocks) for blocks in (1, 3, 6, 144))
        )
        # Electrum returns BTC/kB; the send form expects integer sat/vB.
        fees = [max(1, math.ceil(rate * 100000)) if rate > 0 else 1 for rate in rates]
        fees = [max(fees[i:]) for i in range(len(fees))]
        return dict(
            zip(
                ("fastestFee", "halfHourFee", "hourFee", "economyFee"),
                fees,
                strict=True,
            ),
            minimumFee=1,
        )

    async def broadcast(self, raw: str) -> str:
        return await self.client.broadcast(raw)


class MempoolExplorer:
    def __init__(
        self,
        config: OnchainConfig,
        network: str,
        client: httpx.AsyncClient | None = None,
    ):
        self.client = client or httpx.AsyncClient(
            base_url=mempool_url(config, network) + "/",
            timeout=15,
            follow_redirects=False,
            trust_env=False,
        )

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.client.__aexit__(*args)

    async def checkpoint(self) -> ScanCheckpoint:
        response = await self.client.get("api/blocks/tip/height")
        response.raise_for_status()
        height = int(response.text)
        return ScanCheckpoint(height=height, block_hash=await self.block_hash(height))

    async def block_hash(self, height: int) -> str:
        response = await self.client.get(f"api/block-height/{height}")
        response.raise_for_status()
        block_hash = response.text.strip()
        if not TXID.fullmatch(block_hash):
            raise ValueError("Invalid block hash")
        return block_hash

    async def history(
        self,
        address: str,
        *,
        previous: list[dict] | None = None,
        checkpoint: ScanCheckpoint | None = None,
    ) -> list[dict]:
        cached = {
            tx["txid"]: tx
            for tx in previous or []
            if checkpoint
            and tx["status"]["confirmed"]
            and tx["status"]["block_height"] <= checkpoint.height
        }
        response = await self.client.get(f"api/address/{address}/txs")
        response.raise_for_status()
        page = response.json()
        result: dict[str, dict] = {}
        seen: set[str] = set()
        mempool_full = False
        for _ in range(1000):
            if not isinstance(page, list):
                raise ValueError("Invalid explorer response")
            for tx in page:
                if not TXID.fullmatch(tx["txid"]):
                    raise ValueError("Invalid transaction ID")
                result[tx["txid"]] = tx
            confirmed = [tx for tx in page if tx["status"]["confirmed"]]
            mempool_full = mempool_full or len(page) - len(confirmed) >= 50
            if any(
                tx["txid"] in cached and tx["status"] == cached[tx["txid"]]["status"]
                for tx in confirmed
            ):
                # Only confirmed history covered by the verified checkpoint is
                # retained. Pending or newer entries must come from this scan.
                for txid, tx in cached.items():
                    result.setdefault(txid, tx)
                break
            if len(confirmed) < 25:
                break
            last = confirmed[-1]["txid"]
            if last in seen or not TXID.fullmatch(last):
                raise ValueError("Invalid explorer pagination")
            seen.add(last)
            response = await self.client.get(f"api/address/{address}/txs/chain/{last}")
            response.raise_for_status()
            page = response.json()
        else:
            raise ValueError("Explorer history limit reached")
        # The address endpoint caps pending transactions at 50. Absence from a
        # full page does not mean a previously seen transaction was dropped.
        if mempool_full:
            await self._check_missing_pending(previous or [], result)
        return list(result.values())

    async def _check_missing_pending(self, previous: list[dict], result: dict) -> None:
        for tx in previous:
            if tx["txid"] in result:
                continue
            response = await self.client.get(f"api/tx/{tx['txid']}/status")
            if response.status_code == 404:
                continue
            response.raise_for_status()
            result[tx["txid"]] = {**tx, "status": response.json()}

    async def utxos(self, address: str) -> list[dict]:
        response = await self.client.get(f"api/address/{address}/utxo")
        response.raise_for_status()
        return response.json()

    async def fees(self) -> dict:
        response = await self.client.get("api/v1/fees/recommended")
        response.raise_for_status()
        return response.json()

    async def raw_transaction(self, txid: str) -> str:
        response = await self.client.get(f"api/tx/{txid}/hex")
        response.raise_for_status()
        return response.text.strip()

    async def broadcast(self, raw: str) -> str:
        response = await self.client.post("api/tx", content=raw)
        response.raise_for_status()
        return response.text.strip()


class LnbitsExplorer(BlockExplorerWalletSession):
    def __init__(self, network: str):
        if local_explorer_network() != network:
            raise ValueError("LNbits block explorer is unavailable for this network")
        super().__init__()


Explorer = MempoolExplorer | LnbitsExplorer


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


async def fetch_block_transactions(
    height: int, offset: int = 0, limit: int = 12
) -> BlockTransactions:
    positions = range(offset, offset + limit + 1)
    async with _client() as client:
        results = await asyncio.gather(
            *(client.get_tx_id_from_pos(height, position) for position in positions),
            return_exceptions=True,
        )

    if results and isinstance(results[0], BaseException):
        raise results[0]

    transactions: list[BlockTransaction] = []
    for position, result in zip(positions, results, strict=False):
        if isinstance(result, BaseException) or not isinstance(result, str):
            break
        transactions.append(BlockTransaction(position=position, txid=result))

    return BlockTransactions(
        transactions=transactions[:limit],
        offset=offset,
        has_more=len(transactions) > limit,
    )


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


def local_explorer_network() -> str | None:
    if not settings.lnbits_blockexplorer_enabled:
        return None
    return NETWORKS.get(settings.lnbits_blockexplorer_network)


def provider_name(config: OnchainConfig, network: str) -> str:
    if config.explorer_provider == "auto":
        return "lnbits" if local_explorer_network() == network else "mempool"
    return config.explorer_provider


def mempool_url(config: OnchainConfig, network: str) -> str:
    endpoint = config.mempool_endpoint.rstrip("/")
    # The standard host serves multiple chains; custom URLs identify one chain.
    if endpoint == "https://mempool.space":
        endpoint += {"Mainnet": "", "Testnet": "/testnet", "Testnet4": "/testnet4"}[
            network
        ]
    return endpoint


def explorer_url(config: OnchainConfig, network: str) -> str:
    return (
        "/blockexplorer"
        if provider_name(config, network) == "lnbits"
        else mempool_url(config, network)
    )


def explorer_client(config: OnchainConfig, network: str) -> Explorer:
    if provider_name(config, network) == "lnbits":
        return LnbitsExplorer(network)
    return MempoolExplorer(config, network)


def _client() -> ElectrumClient:
    return ElectrumClient(
        settings.lnbits_blockexplorer_electrum_url,
        network=network_from_name(settings.lnbits_blockexplorer_network),
    )
