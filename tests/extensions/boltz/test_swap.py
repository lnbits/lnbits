import asyncio
import pytest
import pytest_asyncio

from lnbits.extensions.boltz.crud import (
    create_reverse_submarine_swap,
    create_submarine_swap,
    get_reverse_submarine_swap,
    get_submarine_swap,
)
from tests.extensions.boltz.conftest import reverse_swap, swap
from tests.helpers import is_regtest


@pytest.mark.asyncio
async def test_create_swap(client, swap):
    if is_regtest:
        await create_submarine_swap(swap)
        newswap = await get_submarine_swap(swap.id)
        assert newswap.status == "pending"
        assert newswap.boltz_id is not None
        assert newswap.refund_privkey is not None
        assert newswap.refund_address is not None


@pytest.mark.asyncio
async def test_create_reverse_swap(client, reverse_swap):
    if is_regtest:
        swap, wait_for_onchain = reverse_swap
        assert swap.status == "pending"
        assert swap.id is not None
        assert swap.boltz_id is not None
        assert swap.claim_privkey is not None
        assert swap.onchain_address is not None
        assert swap.lockup_address is not None
        newswap = await create_reverse_submarine_swap(swap)
        await wait_for_onchain
        newswap = await get_reverse_submarine_swap(swap.id)
        assert newswap is not None
        assert newswap.status == "complete"
