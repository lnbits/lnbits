import struct
from unittest.mock import AsyncMock

import httpx
import pytest
from embit.script import Script
from embit.transaction import Transaction, TransactionInput, TransactionOutput

from lnbits.core.models.onchain import ScanCheckpoint
from lnbits.core.models.wallets import OnchainConfig
from lnbits.core.services import blockexplorer
from lnbits.utils.electrum import (
    UTXO,
    BlockHeader,
    ElectrumClient,
    HistoryEntry,
    network_from_name,
)


def test_default_provider_matches_enabled_network(settings):
    settings.lnbits_blockexplorer_enabled = False
    assert blockexplorer.provider_name(OnchainConfig(), "Mainnet") == "mempool"
    settings.lnbits_blockexplorer_enabled = True
    for network, name in blockexplorer.NETWORKS.items():
        settings.lnbits_blockexplorer_network = network
        config = OnchainConfig()
        assert blockexplorer.provider_name(config, name) == "lnbits"
        assert blockexplorer.explorer_url(config, name) == "/blockexplorer"
        assert (
            blockexplorer.provider_name(
                config.copy(update={"explorer_provider": "mempool"}), name
            )
            == "mempool"
        )
    assert blockexplorer.provider_name(OnchainConfig(), "Mainnet") == "mempool"
    with pytest.raises(ValueError, match="unavailable"):
        blockexplorer.LnbitsExplorer("Mainnet")
    assert network_from_name("test4") == network_from_name("test")


def test_custom_mempool_url_is_specific_to_network():
    config = OnchainConfig()
    assert (
        blockexplorer.mempool_url(config, "Testnet4")
        == "https://mempool.space/testnet4"
    )
    config.mempool_endpoint = "https://example.com/bitcoin/testnet4/"
    assert (
        blockexplorer.mempool_url(config, "Testnet4")
        == "https://example.com/bitcoin/testnet4"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:3006",
        "http://127.0.0.1:8080",
        "http://192.168.1.2:3006/testnet4",
        "http://[::1]:8080",
    ],
)
async def test_local_mempool_urls_are_allowed(monkeypatch, url):
    real_client = httpx.AsyncClient
    requests = []

    def response(request):
        requests.append(request)
        return httpx.Response(200, json={"fastestFee": 1})

    def client(**kwargs):
        return real_client(**kwargs, transport=httpx.MockTransport(response))

    monkeypatch.setattr(blockexplorer.httpx, "AsyncClient", client)
    async with blockexplorer.MempoolExplorer(
        OnchainConfig(mempool_endpoint=url), "Mainnet"
    ) as provider:
        assert await provider.fees() == {"fastestFee": 1}
    assert str(requests[0].url) == url + "/api/v1/fees/recommended"


@pytest.mark.anyio
async def test_local_explorer_history_coins_fees_and_broadcast(settings, monkeypatch):
    settings.lnbits_blockexplorer_enabled = True
    settings.lnbits_blockexplorer_network = "test4"
    script = Script(bytes.fromhex("0014" + "11" * 20))
    funding = Transaction(
        vin=[TransactionInput(bytes(32), 0xFFFFFFFF)],
        vout=[TransactionOutput(100000, script)],
    )
    spending = Transaction(
        vin=[TransactionInput(funding.txid(), 0)],
        vout=[
            TransactionOutput(75000, script),
            TransactionOutput(20000, Script(bytes.fromhex("0014" + "22" * 20))),
        ],
    )
    funding_id, spending_id = funding.txid().hex(), spending.txid().hex()
    raw = {tx.txid().hex(): tx.serialize().hex() for tx in (funding, spending)}
    client = AsyncMock(spec=ElectrumClient)
    client.network = network_from_name("test4")
    client.get_history.return_value = [
        HistoryEntry(tx_hash=funding_id, height=100),
        HistoryEntry(tx_hash=spending_id, height=0),
    ]
    client.get_transaction.side_effect = lambda txid: raw[txid]
    client.get_block_header.return_value = (
        bytes(68) + struct.pack("<I", 1700000000) + bytes(8)
    ).hex()
    client.get_tip.return_value = BlockHeader(
        height=100, hex=client.get_block_header.return_value
    )
    client.listunspent.return_value = [
        UTXO(tx_hash=spending_id, tx_pos=0, height=0, value=75000)
    ]
    client.estimate_fee.side_effect = [0.00002, 0.000015, 0.00001, -1]
    client.broadcast.return_value = spending_id
    monkeypatch.setattr(blockexplorer, "_client", lambda: client)
    async with blockexplorer.explorer_client(OnchainConfig(), "Testnet4") as provider:
        address = script.address(client.network)
        assert isinstance(address, str)
        history = await provider.history(address)
        assert history[0]["status"]["block_time"] == 1700000000
        assert history[0]["vin"][0]["is_coinbase"]
        assert history[1]["status"] == {"confirmed": False}
        assert history[1]["fee"] == 5000
        assert history[1]["vin"][0]["prevout"]["value"] == 100000
        assert history[1]["vout"][0]["scriptpubkey_address"] == address
        assert (await provider.utxos(address))[0] == {
            "txid": spending_id,
            "vout": 0,
            "value": 75000,
            "status": {"confirmed": False},
        }
        assert await provider.fees() == {
            "fastestFee": 2,
            "halfHourFee": 2,
            "hourFee": 1,
            "economyFee": 1,
            "minimumFee": 1,
        }
        assert await provider.raw_transaction(spending_id) == raw[spending_id]
        assert await provider.broadcast(raw[spending_id]) == spending_id
        client.broadcast.assert_awaited_once_with(raw[spending_id])
        checkpoint = await provider.checkpoint()
        assert await provider.block_hash(100) == checkpoint.block_hash
    client.__aexit__.assert_awaited_once()

    # A new session must reuse persisted details, not just its own raw-tx cache.
    client.get_transaction.reset_mock()
    client.get_block_header.reset_mock()
    async with blockexplorer.explorer_client(OnchainConfig(), "Testnet4") as provider:
        assert (
            await provider.history(address, previous=history, checkpoint=checkpoint)
            == history
        )
        client.get_transaction.assert_not_awaited()
        client.get_block_header.assert_not_awaited()

        # Pending -> confirmed only refreshes status, then a reorg removes the
        # old funding entry and returns the spending transaction to the mempool.
        client.get_history.return_value[1].height = 101
        confirmed = await provider.history(
            address, previous=history, checkpoint=checkpoint
        )
        assert confirmed[1]["status"]["block_height"] == 101
        client.get_block_header.assert_awaited_once_with(101)
        client.get_history.return_value = [HistoryEntry(tx_hash=spending_id, height=0)]
        reorganised = await provider.history(address, previous=confirmed)
        assert len(reorganised) == 1
        assert reorganised[0]["status"] == {"confirmed": False}
        client.get_transaction.assert_not_awaited()

        # A new transaction can also resolve its input from saved outputs.
        payment = Transaction(
            vin=[TransactionInput(spending.txid(), 0)],
            vout=[TransactionOutput(70000, script)],
        )
        payment_id = payment.txid().hex()
        raw[payment_id] = payment.serialize().hex()
        client.get_history.return_value.append(
            HistoryEntry(tx_hash=payment_id, height=0)
        )
        updated = await provider.history(address, previous=reorganised)
        assert updated[-1]["fee"] == 5000
        client.get_transaction.assert_awaited_once_with(payment_id)

        client.get_history.side_effect = TimeoutError
        with pytest.raises(TimeoutError):
            await provider.history(address)


@pytest.mark.anyio
async def test_mempool_provider_uses_custom_url_and_paginates():
    requests = []
    txs = [{"txid": f"{i:064x}", "status": {"confirmed": True}} for i in range(26)]

    def respond(request):
        requests.append(request)
        if "/chain/" in request.url.path:
            return httpx.Response(200, json=txs[25:])
        if request.url.path.endswith("/txs"):
            return httpx.Response(200, json=txs[:25])
        if request.method == "POST":
            return httpx.Response(200, text=txs[0]["txid"])
        return httpx.Response(200, json=[])

    client = httpx.AsyncClient(
        base_url="https://example.com/custom/testnet4/",
        transport=httpx.MockTransport(respond),
    )
    async with blockexplorer.MempoolExplorer(
        OnchainConfig(), "Testnet4", client
    ) as provider:
        assert len(await provider.history("address")) == 26
        assert await provider.broadcast("raw") == txs[0]["txid"]
    assert all(r.url.path.startswith("/custom/testnet4/api/") for r in requests)
    assert requests[-1].content == b"raw"


@pytest.mark.anyio
@pytest.mark.parametrize("use_checkpoint", [False, True])
@pytest.mark.parametrize("new_address", [False, True])
async def test_mempool_history_reuses_only_verified_confirmed_history(
    use_checkpoint, new_address
):
    checkpoint = ScanCheckpoint(height=100, block_hash="b" * 64)
    old = [
        {
            "txid": f"{i:064x}",
            "status": {"confirmed": True, "block_height": 100, "block_hash": "b" * 64},
        }
        for i in range(1, 51)
    ]
    dropped = {"txid": "d" * 64, "status": {"confirmed": False}}
    pending = {"txid": "e" * 64, "status": {"confirmed": False}}
    confirmed = {
        "txid": "f" * 64,
        "status": {"confirmed": True, "block_height": 101, "block_hash": "c" * 64},
    }
    pages = [0, 0, 0]

    def respond(request):
        if request.url.path.endswith("/blocks/tip/height"):
            return httpx.Response(200, text="100")
        if request.url.path.endswith("/block-height/100"):
            return httpx.Response(200, text=checkpoint.block_hash)
        if request.url.path.endswith("/txs"):
            pages[0] += 1
            return httpx.Response(200, json=[pending, confirmed, *old[:24]])
        if request.url.path.endswith(old[23]["txid"]):
            pages[1] += 1
            return httpx.Response(200, json=old[24:49])
        assert request.url.path.endswith(old[48]["txid"])
        pages[2] += 1
        return httpx.Response(200, json=old[49:])

    client = httpx.AsyncClient(
        base_url="https://explorer.test/", transport=httpx.MockTransport(respond)
    )
    async with blockexplorer.MempoolExplorer(
        OnchainConfig(), "Mainnet", client
    ) as provider:
        assert await provider.checkpoint() == checkpoint
        history = await provider.history(
            "address",
            previous=(
                None
                if new_address
                else [*old, dropped, {**confirmed, "status": {"confirmed": False}}]
            ),
            checkpoint=checkpoint if use_checkpoint else None,
        )
    assert {tx["txid"]: tx for tx in history} == {
        tx["txid"]: tx for tx in [pending, confirmed, *old]
    }
    assert pages == ([1, 0, 0] if use_checkpoint and not new_address else [1, 1, 1])


@pytest.mark.anyio
@pytest.mark.parametrize("dropped", [False, True])
@pytest.mark.parametrize("previously_confirmed", [False, True])
async def test_mempool_pending_limit_does_not_drop_cached_transactions(
    dropped, previously_confirmed
):
    pending = [{"txid": f"{i:064x}", "status": {"confirmed": False}} for i in range(51)]

    def respond(request):
        if request.url.path.endswith("/txs"):
            return httpx.Response(200, json=pending[:50])
        assert request.url.path == f"/api/tx/{pending[-1]['txid']}/status"
        return httpx.Response(404 if dropped else 200, json={"confirmed": False})

    client = httpx.AsyncClient(
        base_url="https://explorer.test/", transport=httpx.MockTransport(respond)
    )
    async with blockexplorer.MempoolExplorer(
        OnchainConfig(), "Mainnet", client
    ) as provider:
        previous = [
            *pending[:-1],
            {**pending[-1], "status": {"confirmed": previously_confirmed}},
        ]
        history = await provider.history("address", previous=previous)
    assert history == (pending[:50] if dropped else pending)
