from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import HTTPException

from lnbits.db import Filters
from lnbits.nodes.base import ChannelState
from lnbits.nodes.phoenixd import PhoenixdNode
from lnbits.wallets.base import Feature
from lnbits.wallets.phoenixd import PhoenixdWallet

CHANNEL_ID = "ab" * 32
TXID = "cd" * 32


@pytest.fixture
async def node_factory():
    clients = []

    def create(handler: Callable) -> PhoenixdNode:
        wallet = object.__new__(PhoenixdWallet)
        wallet.client = httpx.AsyncClient(
            base_url="http://phoenixd.test",
            transport=httpx.MockTransport(handler),
        )
        clients.append(wallet.client)
        return PhoenixdNode(wallet)

    yield create
    for client in clients:
        await client.aclose()


@pytest.mark.anyio
async def test_info_balances_states_and_public_redaction(node_factory):
    info = {
        "nodeId": "02" + "ab" * 32,
        "version": "0.9.0",
        "chain": "mainnet",
        "blockHeight": 900000,
        "channels": [
            {
                "state": "Normal",
                "channelId": CHANNEL_ID,
                "balanceSat": 123,
                "inboundLiquiditySat": 456,
                "capacitySat": 600,
                "fundingTxId": TXID,
            },
            {"state": "Offline"},
            {"state": "WaitForFundingConfirmed"},
            {"state": "Closing"},
            {"state": "Closed"},
        ],
    }
    balance = {
        "balanceSat": 200,
        "feeCreditSat": 50,
        "swapIn": {
            "unconfirmedBalanceSat": 10,
            "weaklyConfirmedBalanceSat": 20,
            "deeplyConfirmedBalanceSat": 30,
        },
    }

    def handler(request):
        assert request.url.path in ("/getinfo", "/getbalance")
        return httpx.Response(
            200, json=info if request.url.path == "/getinfo" else balance
        )

    node = node_factory(handler)
    assert node.wallet.__node_cls__ is PhoenixdNode
    assert Feature.nodemanager in node.wallet.features
    result = await node.get_info()
    assert (
        result.balance_msat == 200000
    )  # daemon total, not first channel or fee credit
    assert result.onchain_balance_sat == 60
    assert result.onchain_confirmed_sat == 50
    channels = await node.get_channels()
    assert channels[0].balance.local_msat == 123000
    assert channels[0].balance.remote_msat == 456000
    assert channels[0].balance.total_msat == 600000
    assert channels[0].funding_txid == TXID
    assert channels[0].point is None  # getinfo does not supply an output index
    assert [c.state for c in channels] == [
        ChannelState.ACTIVE,
        ChannelState.INACTIVE,
        ChannelState.PENDING,
        ChannelState.INACTIVE,
        ChannelState.CLOSED,
    ]
    assert await node.get_channel(CHANNEL_ID) == channels[0]
    assert await node.get_channel("missing") is None
    status = await node.get_status()
    assert status.fee_credit_sat == 50
    assert "swapin" in status.capabilities
    public = (await node.get_public_info()).dict()
    assert public["managed_channels"] is True
    assert not {"balance_msat", "fee_credit_sat", "swap_in", "channels"} & public.keys()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "version, actions", [("0.7.3", True), ("0.6.0", False), ("unknown", False)]
)
async def test_empty_node_and_older_versions(node_factory, version, actions):
    node = node_factory(
        lambda r: httpx.Response(
            200,
            json=(
                {"nodeId": "id", "version": version, "chain": "testnet", "channels": []}
                if r.url.path == "/getinfo"
                else {"balanceSat": 0, "feeCreditSat": 5}
            ),
        )
    )
    info = await node.get_info()
    assert info.balance_msat == 0
    assert info.num_peers is None
    assert info.blockheight is None
    assert info.channel_stats.total_capacity == 0
    status = await node.get_status()
    assert ("close" in status.capabilities) == actions
    assert "swapin" not in status.capabilities
    assert status.blockheight is None


@pytest.mark.anyio
async def test_history_units_optional_fields_and_bounded_pagination(node_factory):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("incoming"):
            return httpx.Response(
                200,
                json=[
                    {
                        "isPaid": True,
                        "receivedSat": 42,
                        "paymentHash": CHANNEL_ID,
                        "completedAt": 1700000000123,
                        "expiresAt": 1700003600123,
                    },
                    {
                        "isPaid": False,
                        "receivedSat": 0,
                        "requestedSat": 50,
                        "paymentHash": TXID,
                    },
                    {"isPaid": False, "receivedSat": 0, "paymentHash": "extra"},
                ],
            )
        return httpx.Response(
            200,
            json=[
                {
                    "subType": "splice_out",
                    "isPaid": True,
                    "sent": 12,
                    "fees": 1500,
                    "createdAt": 1700000000123,
                    "txId": TXID,
                    "paymentId": "uuid",
                },
                {
                    "subType": "lightning",
                    "isPaid": False,
                    "sent": 10,
                    "fees": 0,
                    "createdAt": 1700000001123,
                    "paymentHash": CHANNEL_ID,
                },
            ],
        )

    node = node_factory(handler)
    outgoing = await node.get_payments(Filters(limit=2, offset=5))
    assert outgoing.total == 7
    assert outgoing.data[0].amount == 12000
    assert outgoing.data[0].fee == 1500
    assert outgoing.data[0].time == 1700000000
    assert outgoing.data[0].payment_hash is None
    assert outgoing.data[0].txid == TXID
    assert outgoing.data[1].pending
    assert dict(requests[-1].url.params) == {"limit": "3", "offset": "5"}
    incoming = await node.get_invoices(Filters(limit=2))
    assert incoming.total == 3  # next page available, no invented exact total
    assert len(incoming.data) == 2
    assert incoming.data[0].amount == 42000
    assert incoming.data[0].paid_at == 1700000000
    assert incoming.data[0].expiry == 1700003600
    assert incoming.data[0].bolt11 == ""
    assert incoming.data[1].amount == 50000
    assert requests[-1].url.params["all"] == "true"
    await node.get_payments(Filters(limit=10000))
    assert requests[-1].url.params["limit"] == "101"
    with pytest.raises(HTTPException):
        await node.get_payments(Filters(offset=-1))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation,path",
    [("close", "/closechannel"), ("send", "/sendtoaddress"), ("bump", "/bumpfee")],
)
async def test_transactions_form_encoding_and_success(node_factory, operation, path):
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == path
        assert parse_qs(request.content.decode()) == {"feerateSatByte": ["5"]}
        return httpx.Response(200, text=TXID)

    assert (
        await node_factory(handler).transact(operation, {"feerateSatByte": 5}) == TXID
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,body",
    [
        (200, "no channel available"),
        (200, "ChannelFundingResponse.Failure(secret)"),
        (400, "private internal data"),
        (401, "private-password-value"),
        (500, "stack trace"),
    ],
)
async def test_errors_never_report_transaction_success_or_leak_body(
    node_factory, status, body
):
    node = node_factory(lambda r: httpx.Response(status, text=body))
    with pytest.raises(HTTPException) as exc:
        await node.transact("send", {})
    assert exc.value.status_code == 502
    assert body not in exc.value.detail


@pytest.mark.anyio
async def test_timeout_and_malformed_json(node_factory):
    def timeout(request):
        raise httpx.ReadTimeout("sensitive endpoint", request=request)

    with pytest.raises(HTTPException) as exc:
        await node_factory(timeout).transact("close", {})
    assert exc.value.status_code == 504
    assert "before retrying" in exc.value.detail
    with pytest.raises(HTTPException) as invalid:
        await node_factory(lambda r: httpx.Response(200, text="invalid")).get_info()
    assert invalid.value.status_code == 502


@pytest.mark.anyio
async def test_unsupported_operations_do_not_contact_daemon(node_factory):
    def unexpected(request):
        pytest.fail("Unsupported operation reached Phoenixd")

    node = node_factory(unexpected)
    for operation in (
        node.open_channel("peer", 1),
        node.close_channel(force=True),
        node.connect_peer("uri"),
        node.disconnect_peer("id"),
        node.set_channel_fee("id", 1, 1),
    ):
        with pytest.raises(HTTPException) as exc:
            await operation
        assert exc.value.status_code == 501


@pytest.mark.anyio
async def test_liquidity_receive_and_export(node_factory):
    def handler(request):
        path = request.url.path
        if path == "/estimateliquidityfees":
            assert request.url.params["amountSat"] == "2000000"
            return httpx.Response(200, json={"miningFeeSat": 300, "serviceFeeSat": 200})
        if path == "/getswapinaddress":
            return httpx.Response(200, json={"address": "bc1address", "index": 0})
        if path == "/getoffer":
            return httpx.Response(200, text="lno1offer")
        if path == "/getlnaddress":
            return httpx.Response(200, text="must have one channel")
        assert path == "/export" and request.method == "POST"
        return httpx.Response(200, text="exported to /private/daemon/path")

    node = node_factory(handler)
    assert await node.estimate_liquidity(2000000) == {
        "miningFeeSat": 300,
        "serviceFeeSat": 200,
    }
    assert await node.receive_address("swapin") == "bc1address"
    assert await node.receive_address("offer") == "lno1offer"
    with pytest.raises(HTTPException):
        await node.receive_address("lnaddress")
    assert await node.export_history() is None
