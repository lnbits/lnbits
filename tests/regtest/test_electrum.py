"""
Electrum client integration tests against the regtest electrs container.
Requires the regtest docker-compose stack (docker/regtest/docker-compose.yml).
electrs is exposed on localhost:19001 (plain TCP) and localhost:3002 (HTTP).
"""

import asyncio

import httpx
import pytest
from loguru import logger

from lnbits.utils.electrum import ElectrumClient, scripthash_from_scriptpubkey

from .helpers import run_cmd, run_cmd_json

ELECTRS_HOST = "localhost"
ELECTRS_PORT = 19001
ELECTRS_HTTP = "http://localhost:3002"

# bitcoind in the regtest stack uses cookie auth (no -rpcuser/-rpcpassword)
BITCOIN_CLI = [
    "docker",
    "exec",
    "lnbits-bitcoind-1",
    "bitcoin-cli",
    "-rpccookiefile=/root/.bitcoin/regtest/.cookie",
    "-regtest",
]


def bitcoin_height() -> int:
    return run_cmd_json([*BITCOIN_CLI, "getblockchaininfo"])["blocks"]


def mine_blocks(n: int = 1) -> int:
    """Mine n blocks and return the new chain height."""
    run_cmd([*BITCOIN_CLI, "-generate", str(n)])
    return bitcoin_height()


def new_address() -> str:
    return run_cmd([*BITCOIN_CLI, "getnewaddress", "bech32"])


def get_scriptpubkey(address: str) -> bytes:
    info = run_cmd_json([*BITCOIN_CLI, "getaddressinfo", address])
    return bytes.fromhex(info["scriptPubKey"])


def send_to_address(address: str, sats: int) -> str:
    btc = f"{sats * 1e-8:.8f}"
    return run_cmd([*BITCOIN_CLI, "sendtoaddress", address, btc])


async def wait_for_electrs(height: int, timeout: float = 15.0) -> None:
    """Poll electrs HTTP until it has indexed up to `height`."""
    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient() as http:
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await http.get(f"{ELECTRS_HTTP}/blocks/tip/height", timeout=2)
                if int(r.text) >= height:
                    return
            except Exception:
                logger.debug("electrs not ready yet")
            await asyncio.sleep(0.25)
    raise TimeoutError(f"electrs did not reach height {height} within {timeout}s")


@pytest.mark.anyio
async def test_connect_and_height():
    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        before = await client.get_height()

    target = mine_blocks(3)
    await wait_for_electrs(target)

    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        after = await client.get_height()

    assert isinstance(before, int) and before >= 0
    assert after == before + 3


@pytest.mark.anyio
async def test_get_tip():
    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        tip = await client.get_tip()
        assert isinstance(tip.height, int)
        assert isinstance(tip.hex, str)
        assert len(tip.hex) == 160  # 80-byte serialised header


@pytest.mark.anyio
async def test_server_banner():
    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        banner = await client.server_banner()
        assert isinstance(banner, str)


@pytest.mark.anyio
async def test_balance_after_payment():
    address = new_address()
    scripthash = scripthash_from_scriptpubkey(get_scriptpubkey(address))

    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        empty = await client.get_balance(scripthash)
        assert empty.confirmed == 0
        assert empty.unconfirmed == 0

    send_to_address(address, 500_000)
    target = mine_blocks(1)
    await wait_for_electrs(target)

    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        confirmed = await client.get_balance(scripthash)
        assert confirmed.confirmed == 500_000
        assert confirmed.unconfirmed == 0


@pytest.mark.anyio
async def test_history_and_utxos():
    address = new_address()
    scripthash = scripthash_from_scriptpubkey(get_scriptpubkey(address))

    send_to_address(address, 250_000)
    target = mine_blocks(1)
    await wait_for_electrs(target)

    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        history = await client.get_history(scripthash)
        assert len(history) >= 1
        assert history[0].tx_hash
        assert history[0].height > 0

        utxos = await client.listunspent(scripthash)
        assert len(utxos) == 1
        assert utxos[0].value == 250_000

        raw_tx = await client.get_transaction(utxos[0].tx_hash)
        assert isinstance(raw_tx, str) and len(raw_tx) > 0


@pytest.mark.anyio
async def test_subscribe_scripthash_payment():
    address = new_address()
    scripthash = scripthash_from_scriptpubkey(get_scriptpubkey(address))

    received: list = []
    event = asyncio.Event()

    def on_change(params: list) -> None:
        received.append(params)
        event.set()

    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        initial_status = await client.subscribe_scripthash(
            scripthash, callback=on_change
        )
        assert initial_status is None  # fresh address has no history

        send_to_address(address, 777_000)
        target = mine_blocks(1)
        await wait_for_electrs(target)

        await asyncio.wait_for(event.wait(), timeout=10)

        assert len(received) == 1
        assert received[0][0] == scripthash  # first param is the scripthash
        assert received[0][1] is not None  # second param is the new status hash

        balance = await client.get_balance(scripthash)
        assert balance.confirmed == 777_000


@pytest.mark.anyio
async def test_subscribe_headers():
    async with ElectrumClient(f"tcp://{ELECTRS_HOST}:{ELECTRS_PORT}") as client:
        notifications: list = []
        tip = await client.subscribe_headers(callback=lambda p: notifications.append(p))
        height_before = tip.height

        target = mine_blocks(1)
        await wait_for_electrs(target)

        assert await client.get_height() == height_before + 1
