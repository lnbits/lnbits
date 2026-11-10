import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.db import Filters
from lnbits.nodes.cln import CoreLightningNode
from lnbits.utils.cache import Cache


@pytest.mark.anyio
@pytest.mark.parametrize("amount,sent,fee", [(1000, 1010, 10), (1000, 1000, 0)])
async def test_cln_payment_fee(amount: int, sent: int, fee: int, mocker: MockerFixture):
    node = CoreLightningNode(mocker.Mock())
    mocker.patch("lnbits.nodes.cln.cache", Cache())
    mocker.patch.object(
        node,
        "ln_rpc",
        mocker.AsyncMock(
            return_value={
                "pays": [
                    {
                        "amount_msat": amount,
                        "amount_sent_msat": sent,
                        "created_at": 1,
                        "payment_hash": "hash",
                        "status": "complete",
                    }
                ]
            }
        ),
    )

    page = await node.get_payments(Filters())

    assert page.total == 1
    assert page.data[0].amount == amount
    assert page.data[0].fee == fee
