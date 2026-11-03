import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.db import Filters
from lnbits.nodes.cln import CoreLightningNode
from lnbits.utils.cache import Cache


@pytest.mark.anyio
async def test_cln_cached_invoice_pages_keep_their_order(mocker: MockerFixture):
    node = CoreLightningNode(mocker.Mock())
    mocker.patch("lnbits.nodes.cln.cache", Cache())
    invoices = [
        {
            "bolt11": f"invoice-{i}",
            "amount_msat": 1000,
            "payment_hash": f"hash-{i}",
            "status": "unpaid",
            "expires_at": 1000,
        }
        for i in range(4)
    ]
    rpc = mocker.patch.object(
        node, "ln_rpc", mocker.AsyncMock(return_value={"invoices": invoices})
    )

    first = await node.get_invoices(Filters(limit=2))
    second = await node.get_invoices(Filters(limit=2, offset=2))
    repeated = await node.get_invoices(Filters(limit=2))

    assert [i.bolt11 for i in first.data] == ["invoice-3", "invoice-2"]
    assert [i.bolt11 for i in second.data] == ["invoice-1", "invoice-0"]
    assert [i.bolt11 for i in repeated.data] == ["invoice-3", "invoice-2"]
    assert first.total == second.total == repeated.total == 4
    assert [i["bolt11"] for i in invoices] == [f"invoice-{i}" for i in range(4)]
    rpc.assert_awaited_once_with("listinvoices")
