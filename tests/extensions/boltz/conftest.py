import asyncio
import json
import secrets

import pytest
import pytest_asyncio

from lnbits.core.crud import create_account, create_wallet, get_wallet
from lnbits.extensions.boltz.boltz import create_reverse_swap, create_swap
from lnbits.extensions.boltz.crud import (
    create_reverse_submarine_swap,
    create_submarine_swap,
)
from lnbits.extensions.boltz.models import (
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
)
from tests.helpers import credit_wallet, is_regtest


@pytest_asyncio.fixture(scope="session")
async def swap():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="boltz_test")
    data = CreateSubmarineSwap(
        wallet=wallet.id,
        refund_address="bcrt1q3cwq33y435h52gq3qqsdtczh38ltlnf69zvypm",
        amount=50000,
    )
    if is_regtest:
        swap = await create_swap(data)
        # swap = await create_submarine_swap(data)
        return swap


@pytest_asyncio.fixture(scope="session")
async def reverse_swap_fail():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="boltz_test")
    data = CreateReverseSubmarineSwap(
        wallet=wallet.id,
        instant_settlement=True,
        onchain_address="bcrt1q3cwq33y435h52gq3qqsdtczh38ltlnf69zvypm",
        amount=50000,
    )
    if is_regtest:
        return await create_reverse_swap(data)


@pytest_asyncio.fixture(scope="session")
async def reverse_swap():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="boltz_test")
    await credit_wallet(
        wallet_id=wallet.id,
        amount=100000000,
    )
    wallet = await get_wallet(wallet.id)
    assert wallet.balance_msat == 100000000
    data = CreateReverseSubmarineSwap(
        wallet=wallet.id,
        instant_settlement=True,
        onchain_address="bcrt1q3cwq33y435h52gq3qqsdtczh38ltlnf69zvypm",
        amount=50000,
    )
    if is_regtest:
        return await create_reverse_swap(data)
