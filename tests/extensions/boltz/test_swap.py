import pytest
import pytest_asyncio

from lnbits.extensions.boltz.boltz import create_reverse_swap
from tests.extensions.boltz.conftest import reverse_swap, reverse_swap_fail, swap


@pytest.mark.asyncio
async def test_create_swap(client, swap):
    assert swap.status == "pending"
    assert swap.boltz_id is not None
    assert swap.refund_privkey is not None
    assert swap.refund_address is not None


@pytest.mark.asyncio
async def test_create_reverse_swap_fail_insufficient_balance(client, reverse_swap_fail):
    assert reverse_swap_fail == False


@pytest.mark.asyncio
async def test_create_reverse_swap(client, reverse_swap):
    assert reverse_swap.status == "pending"
    assert reverse_swap.boltz_id is not None
    assert reverse_swap.claim_privkey is not None
    assert reverse_swap.onchain_address is not None
    assert reverse_swap.lockup_address is not None
