import pytest
import pytest_asyncio

from tests.extensions.boltz.conftest import reverse_swap, reverse_swap_fail, swap
from tests.helpers import is_regtest


@pytest.mark.asyncio
async def test_create_swap(client, swap):
    if is_regtest:
        assert swap.status == "pending"
        assert swap.boltz_id is not None
        assert swap.refund_privkey is not None
        assert swap.refund_address is not None


@pytest.mark.asyncio
async def test_create_reverse_swap_fail_insufficient_balance(client, reverse_swap_fail):
    if is_regtest:
        assert reverse_swap_fail == False


@pytest.mark.asyncio
async def test_create_reverse_swap(client, reverse_swap):
    if is_regtest:
        swap, wait_for_onchain = reverse_swap
        assert swap.status == "pending"
        assert swap.boltz_id is not None
        assert swap.claim_privkey is not None
        assert swap.onchain_address is not None
        assert swap.lockup_address is not None
        wait_for_onchain.cancel()
        try:
            await wait_for_onchain
        except:
            assert True
