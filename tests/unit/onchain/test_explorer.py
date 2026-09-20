import struct
from unittest.mock import AsyncMock

import httpx
import pytest
from embit.script import Script
from embit.transaction import Transaction, TransactionInput, TransactionOutput

from lnbits.core.services import blockexplorer
from lnbits.onchain import explorer
from lnbits.onchain.models import Config
from lnbits.utils.electrum import UTXO, ElectrumClient, HistoryEntry, network_from_name


def test_default_provider_matches_enabled_network(settings):
    settings.lnbits_blockexplorer_enabled = False
    assert explorer.provider_name(Config()) == "mempool"
    settings.lnbits_blockexplorer_enabled = True
    for network, name in explorer.NETWORKS.items():
        settings.lnbits_blockexplorer_network = network
        config = Config.parse_obj({"network": name})
        assert explorer.provider_name(config) == "lnbits"
        assert explorer.explorer_url(config) == "/blockexplorer"
        assert (
            explorer.provider_name(config.copy(update={"explorer_provider": "mempool"}))
            == "mempool"
        )
    assert explorer.provider_name(Config(network="Mainnet")) == "mempool"
    with pytest.raises(ValueError, match="unavailable"):
        explorer.LnbitsExplorer(Config(network="Mainnet", explorer_provider="lnbits"))
    assert network_from_name("test4") == network_from_name("test")


def test_custom_mempool_url_is_specific_to_network():
    config = Config(network="Testnet4")
    assert explorer.mempool_url(config) == "https://mempool.space/testnet4"
    config.mempool_endpoint = "https://example.com/bitcoin/testnet4/"
    assert explorer.mempool_url(config) == "https://example.com/bitcoin/testnet4"


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

    monkeypatch.setattr(explorer.httpx, "AsyncClient", client)
    async with explorer.MempoolExplorer(Config(mempool_endpoint=url)) as provider:
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
    client.listunspent.return_value = [
        UTXO(tx_hash=spending_id, tx_pos=0, height=0, value=75000)
    ]
    client.estimate_fee.side_effect = [0.00002, 0.000015, 0.00001, -1]
    client.broadcast.return_value = spending_id
    monkeypatch.setattr(blockexplorer, "_client", lambda: client)
    async with explorer.explorer_client(Config(network="Testnet4")) as provider:
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
        client.get_history.side_effect = TimeoutError
        with pytest.raises(TimeoutError):
            await provider.history(address)
    client.__aexit__.assert_awaited_once()


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
    async with explorer.MempoolExplorer(Config(), client) as provider:
        assert len(await provider.history("address")) == 26
        assert await provider.broadcast("raw") == txs[0]["txid"]
    assert all(r.url.path.startswith("/custom/testnet4/api/") for r in requests)
    assert requests[-1].content == b"raw"
