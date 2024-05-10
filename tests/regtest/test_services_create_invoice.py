import pytest
from bolt11 import decode

from lnbits.core.services import (
    create_invoice,
)

descrtiption = "test create invoice"


@pytest.mark.asyncio
async def test_create_invoice(from_wallet):
    payment_hash, pr = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo=descrtiption,
    )
    invoice = decode(pr)
    assert invoice.payment_hash == payment_hash
    assert invoice.amount_msat == 1000000
    assert invoice.description == descrtiption


@pytest.mark.asyncio
async def test_create_internal_invoice(from_wallet):
    payment_hash, pr = await create_invoice(
        wallet_id=from_wallet.id, amount=1000, memo=descrtiption, internal=True
    )
    invoice = decode(pr)
    assert invoice.payment_hash == payment_hash
    assert invoice.amount_msat == 1000000
    assert invoice.description == descrtiption
