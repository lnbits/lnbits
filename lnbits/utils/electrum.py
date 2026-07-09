"""
Electrum protocol client (https://github.com/spesmilo/electrum-protocol).

JSON-RPC 2.0 over TCP / SSL (newline-delimited), with request/response
correlation, subscription dispatch, and automatic keepalive pings.
server.version is sent automatically on connect as required by the spec.
"""

import asyncio
import hashlib
import itertools
import json
import ssl
import struct
from collections.abc import Callable, Coroutine
from typing import Any
from urllib.parse import urlparse

from embit.networks import NETWORKS
from embit.script import Script
from embit.transaction import Transaction as EmbitTransaction
from loguru import logger
from pydantic import BaseModel

DEFAULT_NETWORK = NETWORKS["main"]


def network_from_name(name: str) -> dict:
    """Look up an embit network dict (see embit.networks.NETWORKS) by name."""
    try:
        return NETWORKS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown network {name!r}, expected one of {list(NETWORKS)}"
        ) from exc


class ElectrumError(Exception):
    pass


def scripthash_from_scriptpubkey(scriptpubkey: bytes) -> str:
    """Electrum script hash: SHA-256 of scriptPubKey, byte-reversed to hex."""
    return hashlib.sha256(scriptpubkey).digest()[::-1].hex()


def address_to_scriptpubkey(address: str) -> bytes:
    """Convert a Bitcoin address (P2PKH/P2SH/P2WPKH/P2WSH/P2TR) to scriptPubKey."""
    try:
        return Script.from_address(address).data
    except Exception as exc:
        raise ValueError(f"Invalid address: {address!r}") from exc


def scripthash_from_address(address: str) -> str:
    return scripthash_from_scriptpubkey(address_to_scriptpubkey(address))


_SCRIPT_TYPE_NAMES = {
    "p2pkh": "pubkeyhash",
    "p2sh": "scripthash",
    "p2wpkh": "witness_v0_keyhash",
    "p2wsh": "witness_v0_scripthash",
    "p2tr": "witness_v1_taproot",
}


def _scriptpubkey_info(spk: bytes, network: dict) -> tuple[str, str | None]:
    """Return (type, address_or_None) for a scriptPubKey."""
    n = len(spk)
    # P2PK (not classified by embit)
    if n in (35, 67) and spk[-1] == 0xAC:
        return "pubkey", None
    # OP_RETURN (not classified by embit)
    if n >= 1 and spk[0] == 0x6A:
        return "nulldata", None

    script = Script(spk)
    script_type = script.script_type()
    if script_type is None:
        return "nonstandard", None
    return _SCRIPT_TYPE_NAMES[script_type], script.address(network)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class Balance(BaseModel):
    confirmed: int
    unconfirmed: int


class HistoryEntry(BaseModel):
    tx_hash: str
    height: int
    fee: int | None = None  # present for mempool entries


class MempoolEntry(BaseModel):
    tx_hash: str
    height: int
    fee: int


class UTXO(BaseModel):
    tx_hash: str
    tx_pos: int
    height: int
    value: int  # satoshis


class BlockHeader(BaseModel):
    height: int
    hex: str


class BlockHeaderProof(BaseModel):
    """Returned by get_block_header when cp_height > 0."""

    branch: list[str]
    header: str
    root: str


class BlockHeaders(BaseModel):
    count: int
    hex: str
    max: int


class MerkleProof(BaseModel):
    block_height: int
    merkle: list[str]
    pos: int


class TxIdWithMerkle(BaseModel):
    tx_hash: str
    merkle: list[str]


class FeeHistogramEntry(BaseModel):
    fee_rate: float
    vsize: float


class ServerFeatures(BaseModel):
    class Config:
        extra = "allow"

    genesis_hash: str = ""
    protocol_max: str = ""
    protocol_min: str = ""
    server_version: str = ""
    pruning: int | None = None
    hash_function: str = "sha256d"
    hosts: dict[str, Any] = {}


class ScriptSig(BaseModel):
    hex: str


class ScriptPubKey(BaseModel):
    hex: str
    type: str
    address: str | None = None


class TxInput(BaseModel):
    txid: str | None = None
    vout: int | None = None
    scriptSig: ScriptSig | None = None  # noqa: N815
    sequence: int
    coinbase: str | None = None


class TxOutput(BaseModel):
    value: float
    n: int
    scriptPubKey: ScriptPubKey  # noqa: N815


class Transaction(BaseModel):
    txid: str
    version: int
    locktime: int
    vin: list[TxInput]
    vout: list[TxOutput]
    size: int
    vsize: int
    weight: int
    hex: str


class FeeResponse(BaseModel):
    estimates: dict[str, float]
    histogram: list[FeeHistogramEntry]


class AddressResponse(BaseModel):
    balance: Balance
    history: list[HistoryEntry]
    history_error: str | None = None


class BlockInfo(BaseModel):
    height: int
    hash: str
    timestamp: int
    version: int
    bits: str
    nonce: int
    prev_hash: str
    merkle_root: str


def parse_block_header(header_hex: str, height: int) -> BlockInfo:
    """Parse an 80-byte block header hex string into a BlockInfo model."""
    data = bytes.fromhex(header_hex)
    version = struct.unpack_from("<I", data, 0)[0]
    prev_hash = data[4:36][::-1].hex()
    merkle_root = data[36:68][::-1].hex()
    timestamp = struct.unpack_from("<I", data, 68)[0]
    bits = format(struct.unpack_from("<I", data, 72)[0], "08x")
    nonce = struct.unpack_from("<I", data, 76)[0]
    block_hash = hashlib.sha256(hashlib.sha256(data).digest()).digest()[::-1].hex()
    return BlockInfo(
        height=height,
        hash=block_hash,
        timestamp=timestamp,
        version=version,
        bits=bits,
        nonce=nonce,
        prev_hash=prev_hash,
        merkle_root=merkle_root,
    )


def parse_raw_tx(hex_str: str, network: dict | None = None) -> Transaction:
    """Parse a raw transaction hex string into a Transaction model."""
    network = network or DEFAULT_NETWORK
    data = bytes.fromhex(hex_str)
    tx = EmbitTransaction.parse(data)

    vin: list[TxInput] = []
    for inp in tx.vin:
        if inp.txid == b"\x00" * 32 and inp.vout == 0xFFFFFFFF:
            vin.append(
                TxInput(sequence=inp.sequence, coinbase=inp.script_sig.data.hex())
            )
        else:
            vin.append(
                TxInput(
                    txid=inp.txid.hex(),
                    vout=inp.vout,
                    scriptSig=ScriptSig(hex=inp.script_sig.data.hex()),
                    sequence=inp.sequence,
                )
            )

    vout: list[TxOutput] = []
    for n_out, out in enumerate(tx.vout):
        spk_type, address = _scriptpubkey_info(out.script_pubkey.data, network)
        vout.append(
            TxOutput(
                value=round(out.value / 1e8, 8),
                n=n_out,
                scriptPubKey=ScriptPubKey(
                    hex=out.script_pubkey.data.hex(), type=spk_type, address=address
                ),
            )
        )

    if tx.is_segwit:
        # base (non-witness) size = full size minus the segwit marker/flag
        # (2 bytes) and each input's witness stack
        witness_bytes = sum(len(inp.witness.serialize()) for inp in tx.vin)
        base_size = len(data) - 2 - witness_bytes
        weight = base_size * 3 + len(data)
        vsize = (weight + 3) // 4
    else:
        weight = len(data) * 4
        vsize = len(data)

    return Transaction(
        txid=tx.txid().hex(),
        version=tx.version,
        locktime=tx.locktime,
        vin=vin,
        vout=vout,
        size=len(data),
        vsize=vsize,
        weight=weight,
        hex=hex_str,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ElectrumClient:
    """
    Async Electrum protocol client over plain TCP or SSL.

    Messages are newline-terminated JSON-RPC 2.0, as required by the spec.
    Handles request/response correlation by id, routes push notifications to
    registered callbacks, and sends periodic pings to keep the connection alive.

    Usage::

        # Plain TCP
        async with ElectrumClient("tcp://blockstream.info:110") as client:
            height = await client.get_height()

        # SSL
        async with ElectrumClient("ssl://electrum.blockstream.info:50002") as c:
            height = await c.get_height()
    """

    def __init__(
        self,
        url: str,
        client_name: str = "lnbits",
        protocol_version: str = "1.4",
        ping_interval: float = 60.0,
        network: dict | None = None,
    ) -> None:
        parsed = urlparse(url)
        self.host = parsed.hostname or ""
        self.port = parsed.port or (
            50002 if parsed.scheme in ("ssl", "https") else 50001
        )
        self.use_ssl = parsed.scheme in ("ssl", "https")
        self.client_name = client_name
        self.protocol_version = protocol_version
        self.ping_interval = ping_interval
        self.network = network or DEFAULT_NETWORK
        self._counter = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._subscriptions: dict[str, list[Callable[[list[Any]], Any]]] = {}
        self._recv_task: asyncio.Task[None] | None = None
        self._ping_task: asyncio.Task[None] | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.closed: asyncio.Event = asyncio.Event()
        self.server_version: str = ""
        self.negotiated_protocol: str = ""

    async def connect(self, timeout: float = 10.0) -> None:
        ssl_ctx: ssl.SSLContext | None = None
        if self.use_ssl:
            ssl_ctx = ssl.create_default_context()
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(
                self.host, self.port, ssl=ssl_ctx, limit=4 * 1024 * 1024
            ),
            timeout=timeout,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        result = await self._call(
            "server.version", [self.client_name, self.protocol_version], timeout=timeout
        )
        self.server_version, self.negotiated_protocol = result[0], result[1]
        logger.debug(
            f"Electrum connected: server={self.server_version}"
            f" protocol={self.negotiated_protocol}"
        )
        if self.ping_interval > 0:
            self._ping_task = asyncio.create_task(self._ping_loop())

    async def close(self) -> None:
        for task in (self._ping_task, self._recv_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.debug("Electrum: error while cancelling task")
        self._ping_task = None
        self._recv_task = None
        if self._writer:
            self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=5.0)
            except Exception:
                logger.debug("Electrum: error while closing writer")
        self._reader = None
        self._writer = None

    async def __aenter__(self) -> "ElectrumClient":
        try:
            await self.connect()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ---- internal plumbing ----

    async def _call(
        self,
        method: str,
        params: list[Any] | dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Any:
        if not self._writer:
            raise ElectrumError("Not connected")
        req_id = next(self._counter)
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        self._writer.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "method": method,
                    "params": params if params is not None else [],
                }
            ).encode()
            + b"\n"
        )
        await self._writer.drain()
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise ElectrumError(f"Timeout waiting for response to {method!r}") from exc

    def _dispatch(self, msg: dict[str, Any]) -> None:
        msg_id = msg.get("id")
        if msg_id is not None:
            fut = self._pending.pop(msg_id, None)
            if fut and not fut.done():
                err = msg.get("error")
                if err:
                    fut.set_exception(ElectrumError(err))
                else:
                    fut.set_result(msg.get("result"))
        else:
            method = msg.get("method", "")
            params = msg.get("params", [])
            for cb in list(self._subscriptions.get(method, [])):
                try:
                    result = cb(params)
                    if asyncio.iscoroutine(result):
                        self._bg_tasks.add(asyncio.create_task(result))
                except Exception:
                    logger.exception(f"Electrum: callback error for {method!r}")

    async def _recv_loop(self) -> None:
        assert self._reader
        self._bg_tasks: set[asyncio.Task[Any]] = set()
        buf = b""
        try:
            while True:
                chunk = await self._reader.read(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(f"Electrum: invalid JSON: {line!r}")
                        continue
                    self._dispatch(msg)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Electrum: recv loop error")
        finally:
            self.closed.set()
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ElectrumError("Connection closed"))
            self._pending.clear()

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                await self._call("server.ping")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Electrum: ping loop error")

    # ---- subscription management ----

    def on(self, method: str, callback: Callable[[list[Any]], Any]) -> None:
        """Register a notification callback for a subscription method."""
        self._subscriptions.setdefault(method, []).append(callback)

    def off(self, method: str, callback: Callable[[list[Any]], Any]) -> None:
        """Remove a previously registered notification callback."""
        cbs = self._subscriptions.get(method)
        if cbs and callback in cbs:
            cbs.remove(callback)

    # ---- server methods ----

    async def server_ping(self) -> None:
        await self._call("server.ping")

    async def server_banner(self) -> str:
        return await self._call("server.banner")

    async def server_features(self) -> ServerFeatures:
        data = await self._call("server.features")
        return ServerFeatures.parse_obj(data)

    async def server_peers(self) -> list[Any]:
        return await self._call("server.peers.subscribe")

    # ---- scripthash methods ----

    async def get_balance(self, scripthash: str) -> Balance:
        data = await self._call("blockchain.scripthash.get_balance", [scripthash])
        return Balance.parse_obj(data)

    async def get_history(self, scripthash: str) -> list[HistoryEntry]:
        data = await self._call("blockchain.scripthash.get_history", [scripthash])
        return [HistoryEntry.parse_obj(e) for e in data]

    async def get_mempool(self, scripthash: str) -> list[MempoolEntry]:
        data = await self._call("blockchain.scripthash.get_mempool", [scripthash])
        return [MempoolEntry.parse_obj(e) for e in data]

    async def listunspent(self, scripthash: str) -> list[UTXO]:
        data = await self._call("blockchain.scripthash.listunspent", [scripthash])
        return [UTXO.parse_obj(e) for e in data]

    async def subscribe_scripthash(
        self,
        scripthash: str,
        callback: Callable[[list[Any]], Any] | None = None,
    ) -> str | None:
        """Subscribe to status changes; returns current status hash or None."""
        if callback:
            self.on("blockchain.scripthash.subscribe", callback)
        return await self._call("blockchain.scripthash.subscribe", [scripthash])

    async def unsubscribe_scripthash(
        self,
        scripthash: str,
        callback: Callable[[list[Any]], Any] | None = None,
    ) -> bool:
        if callback:
            self.off("blockchain.scripthash.subscribe", callback)
        return await self._call("blockchain.scripthash.unsubscribe", [scripthash])

    async def subscribe_headers(
        self,
        callback: Callable[[list[Any]], Any] | None = None,
    ) -> BlockHeader:
        """Subscribe to new block headers; returns current tip."""
        if callback:
            self.on("blockchain.headers.subscribe", callback)
        data = await self._call("blockchain.headers.subscribe")
        return BlockHeader.parse_obj(data)

    # ---- transaction methods ----

    async def broadcast(self, raw_tx: str) -> str:
        """Broadcast a raw transaction hex; returns txid on success."""
        return await self._call("blockchain.transaction.broadcast", [raw_tx])

    async def get_transaction(self, txid: str) -> str:
        """Fetch raw transaction hex by txid."""
        return await self._call("blockchain.transaction.get", [txid])

    async def get_merkle(self, txid: str, height: int) -> MerkleProof:
        data = await self._call("blockchain.transaction.get_merkle", [txid, height])
        return MerkleProof.parse_obj(data)

    async def get_tx_id_from_pos(
        self, height: int, tx_pos: int, merkle: bool = False
    ) -> str | TxIdWithMerkle:
        data = await self._call(
            "blockchain.transaction.id_from_pos", [height, tx_pos, merkle]
        )
        if isinstance(data, dict):
            return TxIdWithMerkle.parse_obj(data)
        return data

    # ---- block methods ----

    async def get_tip(self) -> BlockHeader:
        """Returns current chain tip."""
        data = await self._call("blockchain.headers.subscribe")
        return BlockHeader.parse_obj(data)

    async def get_height(self) -> int:
        """Returns the current best block height."""
        return (await self.get_tip()).height

    async def get_block_header(
        self, height: int, cp_height: int = 0
    ) -> str | BlockHeaderProof:
        data = await self._call("blockchain.block.header", [height, cp_height])
        if isinstance(data, dict):
            return BlockHeaderProof.parse_obj(data)
        return data

    async def get_block_headers(
        self, start_height: int, count: int, cp_height: int = 0
    ) -> BlockHeaders:
        data = await self._call(
            "blockchain.block.headers", [start_height, count, cp_height]
        )
        return BlockHeaders.parse_obj(data)

    # ---- fee methods ----

    async def estimate_fee(self, num_blocks: int) -> float:
        """Returns estimated fee rate in BTC/kB for confirmation within num_blocks."""
        return await self._call("blockchain.estimatefee", [num_blocks])

    async def fee_histogram(self) -> list[FeeHistogramEntry]:
        """Returns mempool fee histogram as FeeHistogramEntry(fee_rate, vsize) list."""
        data = await self._call("mempool.get_fee_histogram")
        return [FeeHistogramEntry(fee_rate=r[0], vsize=r[1]) for r in data]


# ---------------------------------------------------------------------------
# Address tracking
# ---------------------------------------------------------------------------


class OnchainAddressEvent(BaseModel):
    address: str
    confirmed: int  # satoshis
    unconfirmed: int  # satoshis
    history: list[HistoryEntry] = []
    history_error: str | None = None

    @property
    def txids(self) -> list[str]:
        return [e.tx_hash for e in self.history]


class AddressTracker:
    """
    Subscribes to a set of Bitcoin addresses over a single shared Electrum
    connection and calls a callback on every balance/history change.
    Addresses can be added/removed at runtime via :meth:`add`/:meth:`remove`,
    and per-connection queues can be attached via :meth:`register_queue` for
    consumers (e.g. websockets) that want events for one specific address.
    Reconnects automatically on failure.

    Args:
        url: Electrum server URL (e.g. ``ssl://electrum.blockstream.info:50002``).
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._ref_counts: dict[str, int] = {}
        self._queues: dict[str, list[asyncio.Queue[OnchainAddressEvent]]] = {}
        self._updated = asyncio.Event()

    def add(self, address: str) -> None:
        """Start tracking an address on the shared connection (ref-counted)."""
        count = self._ref_counts.get(address, 0)
        self._ref_counts[address] = count + 1
        if count == 0:
            self._updated.set()

    def remove(self, address: str) -> None:
        """Decrement ref count; drop the subscription once the last caller leaves."""
        count = self._ref_counts.get(address, 0)
        if count <= 1:
            self._ref_counts.pop(address, None)
            self._updated.set()
        else:
            self._ref_counts[address] = count - 1

    def register_queue(
        self, address: str, queue: "asyncio.Queue[OnchainAddressEvent]"
    ) -> None:
        """Register a per-connection queue to receive events for `address`."""
        self._queues.setdefault(address, []).append(queue)
        self.add(address)

    def unregister_queue(
        self, address: str, queue: "asyncio.Queue[OnchainAddressEvent]"
    ) -> None:
        """Deregister a per-connection queue for `address`."""
        queues = self._queues.get(address, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._queues.pop(address, None)
        self.remove(address)

    async def run(
        self,
        callback: Callable[[OnchainAddressEvent], Coroutine[Any, Any, None]],
        is_active: Callable[[], bool],
    ) -> None:
        while is_active():
            try:
                await self._run_once(callback, is_active)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not is_active():
                    return
                logger.warning(f"AddressTracker: {exc!s}, retrying in 5s")
                await asyncio.sleep(5)

    async def _run_once(
        self,
        callback: Callable[[OnchainAddressEvent], Coroutine[Any, Any, None]],
        is_active: Callable[[], bool],
    ) -> None:
        async with ElectrumClient(self.url) as client:
            subscribed: dict[str, str] = {}  # scripthash -> address

            async def on_status_change(params: list[Any]) -> None:
                if not params:
                    return
                address = subscribed.get(params[0])
                if address:
                    await self._fetch_and_dispatch(client, address, params[0], callback)

            client.on("blockchain.scripthash.subscribe", on_status_change)

            while is_active():
                self._updated.clear()
                await self._sync_subscriptions(client, subscribed, callback)
                if await self._wait_for_change_or_close(client):
                    break  # connection closed; reconnect

    async def _sync_subscriptions(
        self,
        client: ElectrumClient,
        subscribed: dict[str, str],
        callback: Callable[[OnchainAddressEvent], Coroutine[Any, Any, None]],
    ) -> None:
        wanted = {a: scripthash_from_address(a) for a in self._ref_counts}
        for address, scripthash in wanted.items():
            if scripthash not in subscribed:
                subscribed[scripthash] = address
                await client.subscribe_scripthash(scripthash)
                await self._fetch_and_dispatch(client, address, scripthash, callback)
        still_wanted = set(wanted.values())
        for scripthash, address in list(subscribed.items()):
            if address not in still_wanted:
                del subscribed[scripthash]
                await client.unsubscribe_scripthash(scripthash)

    async def _wait_for_change_or_close(self, client: ElectrumClient) -> bool:
        """Waits until addresses change or the connection closes; returns True
        if it was the connection that closed."""
        wait_task = asyncio.create_task(self._updated.wait())
        closed_task = asyncio.create_task(client.closed.wait())
        try:
            done, _ = await asyncio.wait(
                [wait_task, closed_task],
                timeout=30,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for t in (wait_task, closed_task):
                if not t.done():
                    t.cancel()
        return closed_task in done

    async def _fetch_and_dispatch(
        self,
        client: ElectrumClient,
        address: str,
        scripthash: str,
        callback: Callable[[OnchainAddressEvent], Coroutine[Any, Any, None]],
    ) -> None:
        balance_r, history_r, mempool_r = await asyncio.gather(
            client.get_balance(scripthash),
            client.get_history(scripthash),
            client.get_mempool(scripthash),
            return_exceptions=True,
        )
        if isinstance(balance_r, BaseException):
            raise balance_r
        history: list[HistoryEntry] = (
            [] if isinstance(history_r, BaseException) else history_r
        )
        history_error: str | None = (
            str(history_r) if isinstance(history_r, BaseException) else None
        )
        if not isinstance(mempool_r, BaseException):
            seen = {e.tx_hash for e in history}
            for m in mempool_r:
                if m.tx_hash not in seen:
                    history.append(HistoryEntry(tx_hash=m.tx_hash, height=0, fee=m.fee))
        event = OnchainAddressEvent(
            address=address,
            confirmed=balance_r.confirmed,
            unconfirmed=balance_r.unconfirmed,
            history=history,
            history_error=history_error,
        )
        for q in list(self._queues.get(address, [])):
            q.put_nowait(event)
        await callback(event)


# ---------------------------------------------------------------------------
# Transaction tracking
# ---------------------------------------------------------------------------


class OnchainTxEvent(BaseModel):
    txid: str
    confirmed: bool
    height: int | None = None
    fee: int | None = None


def tx_watch_scripthash(tx: Transaction) -> str | None:
    """Return the scripthash of the first spendable output, used to subscribe
    for confirmation notifications."""
    for out in tx.vout:
        if out.scriptPubKey.type != "nulldata":
            return scripthash_from_scriptpubkey(bytes.fromhex(out.scriptPubKey.hex))
    return None


class TransactionTracker:
    """
    Subscribes to a Bitcoin transaction via Electrum and calls a callback on
    each status change (unconfirmed → confirmed).  Stops automatically once
    the transaction is confirmed or ``is_active()`` returns ``False``.
    Per-connection queues can be attached via :meth:`register_queue` for
    consumers (e.g. websockets) that want events for this transaction.

    Args:
        url: Electrum server URL (e.g. ``ssl://electrum.blockstream.info:50002``).
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._queues: list[asyncio.Queue[OnchainTxEvent]] = []

    def register_queue(self, queue: "asyncio.Queue[OnchainTxEvent]") -> None:
        """Register a per-connection queue to receive events for this tx."""
        self._queues.append(queue)

    def unregister_queue(self, queue: "asyncio.Queue[OnchainTxEvent]") -> None:
        """Deregister a per-connection queue."""
        if queue in self._queues:
            self._queues.remove(queue)

    def has_queues(self) -> bool:
        return bool(self._queues)

    async def track(
        self,
        txid: str,
        callback: Callable[[OnchainTxEvent], Coroutine[Any, Any, None]],
        is_active: Callable[[], bool],
    ) -> None:
        while is_active():
            try:
                confirmed = await self._track_once(txid, callback, is_active)
                if confirmed:
                    return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not is_active():
                    return
                logger.warning(
                    f"TransactionTracker {txid[:8]}: {exc!s}, retrying in 5s"
                )
                await asyncio.sleep(5)

    async def _track_once(
        self,
        txid: str,
        callback: Callable[[OnchainTxEvent], Coroutine[Any, Any, None]],
        is_active: Callable[[], bool],
    ) -> bool:
        """One connection attempt; returns True if the tx is confirmed."""
        async with ElectrumClient(self.url) as client:
            try:
                raw = await client.get_transaction(txid)
            except ElectrumError as exc:
                logger.warning(f"TransactionTracker {txid[:8]}: {exc!s}")
                await asyncio.sleep(10)
                return False

            scripthash = tx_watch_scripthash(parse_raw_tx(raw))
            confirmed_event = asyncio.Event()

            async def on_change(
                params: list[Any],
                _sh: str | None = scripthash,
                _done: asyncio.Event = confirmed_event,
            ) -> None:
                if params and params[0] == _sh:
                    ev = await self._fetch_status(client, txid, _sh)
                    await self._dispatch(ev, callback)
                    if ev.confirmed:
                        _done.set()

            if scripthash:
                await client.subscribe_scripthash(scripthash, on_change)

            event = await self._fetch_status(client, txid, scripthash)
            await self._dispatch(event, callback)
            if event.confirmed:
                return True

            while is_active() and not confirmed_event.is_set():
                try:
                    await asyncio.wait_for(client.closed.wait(), timeout=30)
                    break  # connection closed; reconnect
                except asyncio.TimeoutError:
                    pass
            return confirmed_event.is_set()

    async def _dispatch(
        self,
        event: OnchainTxEvent,
        callback: Callable[[OnchainTxEvent], Coroutine[Any, Any, None]],
    ) -> None:
        for q in list(self._queues):
            q.put_nowait(event)
        await callback(event)

    @staticmethod
    async def _fetch_status(
        client: ElectrumClient, txid: str, scripthash: str | None
    ) -> OnchainTxEvent:
        if scripthash:
            try:
                for entry in await client.get_history(scripthash):
                    if entry.tx_hash == txid:
                        return OnchainTxEvent(
                            txid=txid,
                            confirmed=entry.height > 0,
                            height=entry.height if entry.height > 0 else None,
                            fee=entry.fee,
                        )
            except ElectrumError:
                try:
                    for m in await client.get_mempool(scripthash):
                        if m.tx_hash == txid:
                            return OnchainTxEvent(txid=txid, confirmed=False, fee=m.fee)
                    return OnchainTxEvent(txid=txid, confirmed=True)
                except ElectrumError:
                    pass
        return OnchainTxEvent(txid=txid, confirmed=False)


# ---------------------------------------------------------------------------
# Block tracking
# ---------------------------------------------------------------------------


class BlockTracker:
    """
    Subscribes to new block headers via Electrum and dispatches them to
    registered queues.  Per-connection queues can be attached via
    :meth:`register_queue`.  Reconnects automatically on failure.

    Args:
        url: Electrum server URL (e.g. ``ssl://electrum.blockstream.info:50002``).
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._queues: list[asyncio.Queue[BlockInfo]] = []

    def register_queue(self, queue: "asyncio.Queue[BlockInfo]") -> None:
        """Register a per-connection queue to receive new block events."""
        self._queues.append(queue)

    def unregister_queue(self, queue: "asyncio.Queue[BlockInfo]") -> None:
        """Deregister a per-connection queue."""
        if queue in self._queues:
            self._queues.remove(queue)

    def has_queues(self) -> bool:
        return bool(self._queues)

    async def run(
        self,
        callback: Callable[[BlockInfo], Coroutine[Any, Any, None]],
        is_active: Callable[[], bool],
    ) -> None:
        while is_active():
            try:
                await self._run_once(callback, is_active)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not is_active():
                    return
                logger.warning(f"BlockTracker: {exc!s}, retrying in 5s")
                await asyncio.sleep(5)

    async def _run_once(
        self,
        callback: Callable[[BlockInfo], Coroutine[Any, Any, None]],
        is_active: Callable[[], bool],
    ) -> None:
        async with ElectrumClient(self.url) as client:

            async def on_header(params: list[Any]) -> None:
                h = params[0]
                event = parse_block_header(h["hex"], h["height"])
                await self._dispatch(event, callback)

            tip = await client.subscribe_headers(on_header)
            await self._dispatch(parse_block_header(tip.hex, tip.height), callback)

            while is_active():
                try:
                    await asyncio.wait_for(client.closed.wait(), timeout=30)
                    break  # connection closed; reconnect
                except asyncio.TimeoutError:
                    pass

    async def _dispatch(
        self,
        event: BlockInfo,
        callback: Callable[[BlockInfo], Coroutine[Any, Any, None]],
    ) -> None:
        for q in list(self._queues):
            q.put_nowait(event)
        await callback(event)
