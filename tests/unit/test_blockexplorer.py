from types import TracebackType

import pytest
from pytest_mock import MockerFixture

from lnbits.core.services import blockexplorer
from lnbits.utils.electrum import ElectrumError


class MockElectrumClient:
    async def __aenter__(self) -> "MockElectrumClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def get_tx_id_from_pos(
        self, height: int, position: int, merkle: bool = False
    ) -> str:
        assert height == 965_482
        assert merkle is False
        if position >= 15:
            raise ElectrumError("No transaction at position")
        return f"{position:064x}"


@pytest.mark.anyio
async def test_fetch_block_transactions_is_paginated(mocker: MockerFixture) -> None:
    mocker.patch.object(blockexplorer, "_client", return_value=MockElectrumClient())

    first_page = await blockexplorer.fetch_block_transactions(965_482, 0, 12)
    last_page = await blockexplorer.fetch_block_transactions(965_482, 12, 12)

    assert len(first_page.transactions) == 12
    assert first_page.transactions[0].position == 0
    assert first_page.has_more is True
    assert [transaction.position for transaction in last_page.transactions] == [
        12,
        13,
        14,
    ]
    assert last_page.has_more is False


@pytest.mark.anyio
async def test_fetch_block_transactions_propagates_first_error(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(blockexplorer, "_client", return_value=MockElectrumClient())

    with pytest.raises(ElectrumError, match="No transaction"):
        await blockexplorer.fetch_block_transactions(965_482, 15, 12)
