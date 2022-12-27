import pytest_asyncio

from lnbits.extensions.boltz.models import CreateReverseSubmarineSwap


@pytest_asyncio.fixture(scope="session")
async def reverse_swap(from_wallet):
    data = CreateReverseSubmarineSwap(
        wallet=from_wallet.id,
        instant_settlement=True,
        onchain_address="bcrt1q4vfyszl4p8cuvqh07fyhtxve5fxq8e2ux5gx43",
        amount=20_000,
    )
    return data
