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
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from pydantic import BaseModel


class ElectrumError(Exception):
    pass


def scripthash_from_scriptpubkey(scriptpubkey: bytes) -> str:
    """Electrum script hash: SHA-256 of scriptPubKey, byte-reversed to hex."""
    return hashlib.sha256(scriptpubkey).digest()[::-1].hex()


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
        self._counter = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._subscriptions: dict[str, list[Callable[[list[Any]], Any]]] = {}
        self._recv_task: asyncio.Task[None] | None = None
        self._ping_task: asyncio.Task[None] | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
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

    async def get_transaction(
        self, txid: str, verbose: bool = False
    ) -> str | dict[str, Any]:
        return await self._call("blockchain.transaction.get", [txid, verbose])

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
