import asyncio
import json
import secrets

import pytest
import pytest_asyncio

from lnbits.core.crud import create_account, create_wallet, get_wallet
from lnbits.extensions.boltz.boltz import create_reverse_swap, create_swap
from lnbits.extensions.boltz.models import (
    CreateReverseSubmarineSwap,
    CreateSubmarineSwap,
)
from tests.helpers import credit_wallet, is_regtest
from tests.mocks import WALLET


@pytest_asyncio.fixture(scope="session")
async def swap(from_wallet):
    data = CreateSubmarineSwap(
        wallet=from_wallet.id,
        refund_address="bcrt1q3cwq33y435h52gq3qqsdtczh38ltlnf69zvypm",
        amount=50_000,
    )
    if is_regtest:
        return await create_swap(data)


@pytest_asyncio.fixture(scope="session")
async def reverse_swap(from_wallet):
    data = CreateReverseSubmarineSwap(
        wallet=from_wallet.id,
        instant_settlement=True,
        onchain_address="bcrt1q4vfyszl4p8cuvqh07fyhtxve5fxq8e2ux5gx43",
        amount=50_000,
    )
    if is_regtest:
        return await create_reverse_swap(data)
