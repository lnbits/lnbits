import pytest
from bolt11 import decode

from lnbits.core.services import (
    PaymentPendingStatus,
    create_invoice,
)
from lnbits.wallets import get_funding_source

description = "test create invoice"


@pytest.mark.asyncio
async def test_create_invoice(from_wallet):
    payment_hash, pr = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo=description,
    )
    invoice = decode(pr)
    assert invoice.payment_hash == payment_hash
    assert invoice.amount_msat == 1000000
    assert invoice.description == description

    funding_source = get_funding_source()
    status = await funding_source.get_invoice_status(payment_hash)
    assert isinstance(status, PaymentPendingStatus)


@pytest.mark.asyncio
async def test_create_internal_invoice(from_wallet):
    payment_hash, pr = await create_invoice(
        wallet_id=from_wallet.id, amount=1000, memo=description, internal=True
    )
    invoice = decode(pr)
    assert invoice.payment_hash == payment_hash
    assert invoice.amount_msat == 1000000
    assert invoice.description == description

    funding_source = get_funding_source()
    status = await funding_source.get_invoice_status(payment_hash)
    assert isinstance(status, PaymentPendingStatus)
