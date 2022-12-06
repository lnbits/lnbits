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
from tests.mocks import WALLET


@pytest_asyncio.fixture(scope="session")
async def reverse_swap(from_wallet):
    data = CreateReverseSubmarineSwap(
        wallet=from_wallet.id,
        instant_settlement=True,
        onchain_address="bcrt1q4vfyszl4p8cuvqh07fyhtxve5fxq8e2ux5gx43",
        amount=20_000,
    )
    return await create_reverse_swap(data)
