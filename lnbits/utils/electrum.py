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

from bech32 import (
    CHARSET,
    bech32_hrp_expand,
    bech32_polymod,
    convertbits,
)
from bech32 import encode as bech32_segwit_encode
from loguru import logger
from pydantic import BaseModel

_BECH32M_CONST = 0x2BC830A3  # BIP-350


def _segwit_addr_decode(address: str) -> tuple[int, bytes]:
    """Decode a segwit address, supporting bech32 (v0) and bech32m (v1+)."""
    lower = address.lower()
    pos = lower.rfind("1")
    if (
        pos < 1
        or pos + 7 > len(lower)
        or not all(c in CHARSET for c in lower[pos + 1 :])
    ):
        raise ValueError(f"Invalid bech32 address: {address!r}")
    hrp = lower[:pos]
    data = [CHARSET.find(c) for c in lower[pos + 1 :]]
    const = bech32_polymod(bech32_hrp_expand(hrp) + data)
    if const not in (1, _BECH32M_CONST):
        raise ValueError(f"Invalid bech32 address: {address!r}")
    payload = data[:-6]
    witness_version = payload[0]
    bits = convertbits(payload[1:], 5, 8, False)
    if bits is None:
        raise ValueError(f"Invalid bech32 witness program in address: {address!r}")
    expected = 1 if witness_version == 0 else _BECH32M_CONST
    if const != expected:
        raise ValueError(
            f"Wrong bech32 variant for witness version {witness_version}: {address!r}"
        )
    return witness_version, bytes(bits)


def _bech32m_encode(hrp: str, witver: int, witprog: bytes) -> str:
    """Encode a segwit address with bech32m checksum (witness version 1+)."""
    data = [witver] + (convertbits(list(witprog), 8, 5) or [])
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod([*values, 0, 0, 0, 0, 0, 0]) ^ _BECH32M_CONST
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(CHARSET[d] for d in data + checksum)


class ElectrumError(Exception):
    pass


def scripthash_from_scriptpubkey(scriptpubkey: bytes) -> str:
    """Electrum script hash: SHA-256 of scriptPubKey, byte-reversed to hex."""
    return hashlib.sha256(scriptpubkey).digest()[::-1].hex()


_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58decode_check(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + _B58_ALPHABET.index(c)
    nz = len(s) - len(s.lstrip("1"))
    buf: list[int] = []
    while n:
        n, rem = divmod(n, 256)
        buf.insert(0, rem)
    raw = bytes([0] * nz + buf)
    payload, chk = raw[:-4], raw[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if chk != expected:
        raise ValueError(f"Bad base58check checksum: {s!r}")
    return payload  # byte 0 = version, bytes 1:21 = hash160


def address_to_scriptpubkey(address: str) -> bytes:
    """Convert a Bitcoin address (P2PKH/P2SH/P2WPKH/P2WSH/P2TR) to scriptPubKey."""
    lower = address.lower()
    if lower.startswith(("bc1", "tb1", "bcrt1")):
        witness_version, witness_prog = _segwit_addr_decode(address)
        ver_op = 0x00 if witness_version == 0 else (0x50 + witness_version)
        return bytes([ver_op, len(witness_prog)]) + witness_prog
    else:
        payload = _b58decode_check(address)
        version, hash160 = payload[0], payload[1:]
        if version in (0x00, 0x6F, 0x41):  # P2PKH mainnet/testnet/regtest
            return bytes([0x76, 0xA9, 0x14]) + hash160 + bytes([0x88, 0xAC])
        if version in (0x05, 0xC4, 0x3A):  # P2SH mainnet/testnet/regtest
            return bytes([0xA9, 0x14]) + hash160 + bytes([0x87])
        raise ValueError(f"Unknown address version byte: {version:#04x}")


def scripthash_from_address(address: str) -> str:
    return scripthash_from_scriptpubkey(address_to_scriptpubkey(address))


def _b58encode_check(payload: bytes) -> str:
    chk = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(payload + chk, "big")
    chars: list[str] = []
    while n:
        n, rem = divmod(n, 58)
        chars.insert(0, _B58_ALPHABET[rem])
    nz = len(payload) - len(payload.lstrip(b"\x00"))
    return _B58_ALPHABET[0] * nz + "".join(chars)


def _read_varint(data: bytes, i: int) -> tuple[int, int]:
    b = data[i]
    if b < 0xFD:
        return b, i + 1
    if b == 0xFD:
        return struct.unpack_from("<H", data, i + 1)[0], i + 3
    if b == 0xFE:
        return struct.unpack_from("<I", data, i + 1)[0], i + 5
    return struct.unpack_from("<Q", data, i + 1)[0], i + 9


def _scriptpubkey_info(script: bytes) -> tuple[str, str | None]:
    """Return (type, address_or_None) for a scriptPubKey."""
    n = len(script)
    # P2PKH
    if n == 25 and script[:3] == b"\x76\xa9\x14" and script[23:] == b"\x88\xac":
        return "pubkeyhash", _b58encode_check(b"\x00" + script[3:23])
    # P2SH
    if n == 23 and script[0] == 0xA9 and script[1] == 0x14 and script[22] == 0x87:
        return "scripthash", _b58encode_check(b"\x05" + script[2:22])
    # P2WPKH
    if n == 22 and script[0] == 0x00 and script[1] == 0x14:
        return "witness_v0_keyhash", bech32_segwit_encode("bc", 0, list(script[2:]))
    # P2WSH
    if n == 34 and script[0] == 0x00 and script[1] == 0x20:
        return "witness_v0_scripthash", bech32_segwit_encode("bc", 0, list(script[2:]))
    # P2TR
    if n == 34 and script[0] == 0x51 and script[1] == 0x20:
        return "witness_v1_taproot", _bech32m_encode("bc", 1, script[2:])
    # P2PK
    if n in (35, 67) and script[-1] == 0xAC:
        return "pubkey", None
    # OP_RETURN
    if n >= 1 and script[0] == 0x6A:
        return "nulldata", None
    return "nonstandard", None


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


def parse_raw_tx(hex_str: str) -> Transaction:
    """Parse a raw transaction hex string into a Transaction model."""
    data = bytes.fromhex(hex_str)
    i = 0

    version = struct.unpack_from("<I", data, i)[0]
    i += 4

    segwit = len(data) > i + 1 and data[i] == 0x00 and data[i + 1] == 0x01
    if segwit:
        i += 2

    vin_start = i
    vin_count, i = _read_varint(data, i)
    vin: list[TxInput] = []
    for _ in range(vin_count):
        prev_txid = data[i : i + 32][::-1].hex()
        i += 32
        prev_vout = struct.unpack_from("<I", data, i)[0]
        i += 4
        script_len, i = _read_varint(data, i)
        script_sig_hex = data[i : i + script_len].hex()
        i += script_len
        sequence = struct.unpack_from("<I", data, i)[0]
        i += 4
        if prev_txid == "0" * 64 and prev_vout == 0xFFFFFFFF:
            vin.append(TxInput(sequence=sequence, coinbase=script_sig_hex))
        else:
            vin.append(
                TxInput(
                    txid=prev_txid,
                    vout=prev_vout,
                    scriptSig=ScriptSig(hex=script_sig_hex),
                    sequence=sequence,
                )
            )

    vout_count, i = _read_varint(data, i)
    vout: list[TxOutput] = []
    for n_out in range(vout_count):
        value_sat = struct.unpack_from("<Q", data, i)[0]
        i += 8
        script_len, i = _read_varint(data, i)
        spk_bytes = data[i : i + script_len]
        i += script_len
        spk_type, address = _scriptpubkey_info(spk_bytes)
        vout.append(
            TxOutput(
                value=round(value_sat / 1e8, 8),
                n=n_out,
                scriptPubKey=ScriptPubKey(
                    hex=spk_bytes.hex(), type=spk_type, address=address
                ),
            )
        )

    vout_end = i

    if segwit:
        for _ in range(vin_count):
            items, i = _read_varint(data, i)
            for _ in range(items):
                item_len, i = _read_varint(data, i)
                i += item_len

    locktime_start = i
    locktime = struct.unpack_from("<I", data, i)[0]

    if segwit:
        non_witness = (
            data[:4]
            + data[vin_start:vout_end]
            + data[locktime_start : locktime_start + 4]
        )
        txid = hashlib.sha256(hashlib.sha256(non_witness).digest()).digest()[::-1].hex()
        base_size = 4 + (vout_end - vin_start) + 4
        weight = base_size * 3 + len(data)
        vsize = (weight + 3) // 4
    else:
        txid = hashlib.sha256(hashlib.sha256(data).digest()).digest()[::-1].hex()
        weight = len(data) * 4
        vsize = len(data)

    return Transaction(
        txid=txid,
        version=version,
        locktime=locktime,
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
    Addresses can be added/removed at runtime via :meth:`add`/:meth:`remove`.
    Reconnects automatically on failure.

    Args:
        url: Electrum server URL (e.g. ``ssl://electrum.blockstream.info:50002``).
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._addresses: set[str] = set()
        self._updated = asyncio.Event()

    def add(self, address: str) -> None:
        """Start tracking an address on the shared connection."""
        if address not in self._addresses:
            self._addresses.add(address)
            self._updated.set()

    def remove(self, address: str) -> None:
        """Stop tracking an address on the shared connection."""
        if address in self._addresses:
            self._addresses.discard(address)
            self._updated.set()

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
        wanted = {a: scripthash_from_address(a) for a in self._addresses}
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

    @staticmethod
    async def _fetch_and_dispatch(
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
        await callback(
            OnchainAddressEvent(
                address=address,
                confirmed=balance_r.confirmed,
                unconfirmed=balance_r.unconfirmed,
                history=history,
                history_error=history_error,
            )
        )


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

    Args:
        url: Electrum server URL (e.g. ``ssl://electrum.blockstream.info:50002``).
    """

    def __init__(self, url: str) -> None:
        self.url = url

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
                    await callback(ev)
                    if ev.confirmed:
                        _done.set()

            if scripthash:
                await client.subscribe_scripthash(scripthash, on_change)

            event = await self._fetch_status(client, txid, scripthash)
            await callback(event)
            if event.confirmed:
                return True

            while is_active() and not confirmed_event.is_set():
                try:
                    await asyncio.wait_for(client.closed.wait(), timeout=30)
                    break  # connection closed; reconnect
                except asyncio.TimeoutError:
                    pass
            return confirmed_event.is_set()

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
    Subscribes to new block headers via Electrum and calls a callback on
    every new block.  Reconnects automatically on failure.

    Args:
        url: Electrum server URL (e.g. ``ssl://electrum.blockstream.info:50002``).
    """

    def __init__(self, url: str) -> None:
        self.url = url

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
                await callback(parse_block_header(h["hex"], h["height"]))

            tip = await client.subscribe_headers(on_header)
            await callback(parse_block_header(tip.hex, tip.height))

            while is_active():
                try:
                    await asyncio.wait_for(client.closed.wait(), timeout=30)
                    break  # connection closed; reconnect
                except asyncio.TimeoutError:
                    pass
