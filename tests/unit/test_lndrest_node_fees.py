import httpx
import pytest

from lnbits.nodes.base import NodeFees
from lnbits.nodes.lndrest import LndRestNode
from lnbits.wallets.lndrest import LndRestWallet


@pytest.mark.anyio
@pytest.mark.parametrize(
    "day, week, month",
    [(0, 0, 0), (1, 23, 456), (9007199254740993, 9007199254740994, 9007199254740995)],
)
async def test_lnd_fee_revenue_is_reported_in_millisatoshis(day, week, month):
    responses = {
        "/v1/getinfo": {
            "identity_pubkey": "02" + "ab" * 32,
            "color": "#ffffff",
            "alias": "test node",
            "num_peers": 0,
            "block_height": 900000,
            "uris": [],
        },
        "/v1/channels": {"channels": []},
        "/v1/channels/pending": {
            "pending_open_channels": [],
            "pending_force_closing_channels": [],
            "waiting_close_channels": [],
        },
        "/v1/channels/closed": {"channels": []},
        "/v1/balance/blockchain": {"total_balance": "77", "confirmed_balance": "66"},
        "/v1/fees": {
            "day_fee_sum": str(day),
            "week_fee_sum": str(week),
            "month_fee_sum": str(month),
        },
        "/v1/balance/channels": {"local_balance": {"msat": "7890"}},
    }

    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json=responses[request.url.path])

    wallet = object.__new__(LndRestWallet)
    wallet.endpoint = "http://lnd.test"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        wallet.client = client
        info = await LndRestNode(wallet).get_info()

    assert info.fees == NodeFees(
        total_msat=0,
        daily_msat=day * 1000,
        weekly_msat=week * 1000,
        monthly_msat=month * 1000,
    )
    assert info.onchain_balance_sat == 77
    assert info.onchain_confirmed_sat == 66
    assert info.balance_msat == 7890
