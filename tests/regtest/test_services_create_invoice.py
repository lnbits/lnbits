import hashlib

import pytest
from bolt11 import decode

from lnbits.core.services import (
    create_invoice,
)
from lnbits.settings import settings
from lnbits.wallets import get_funding_source
from lnbits.wallets.base import PaymentStatus

from .helpers import is_boltz_wallet

description = "test create invoice"


@pytest.mark.anyio
async def test_create_invoice(from_wallet):
    payment = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo=description,
    )

    # Boltz and NWC may omit the preimage until the invoice is paid.
    if not is_boltz_wallet and settings.lnbits_backend_wallet_class != "NWCWallet":
        assert payment.preimage

    invoice = decode(payment.bolt11)
    assert invoice.payment_hash == payment.payment_hash
    assert invoice.amount_msat == 1000000
    if settings.lnbits_backend_wallet_class == "NWCWallet":
        # The provider puts the description's hash in the BOLT11 invoice.
        assert (
            invoice.description_hash == hashlib.sha256(description.encode()).hexdigest()
        )
    else:
        assert invoice.description == description

    funding_source = get_funding_source()
    status = await funding_source.get_invoice_status(payment.payment_hash)
    assert isinstance(status, PaymentStatus)
    assert status.pending


@pytest.mark.anyio
async def test_create_internal_invoice(from_wallet):
    payment = await create_invoice(
        wallet_id=from_wallet.id, amount=1000, memo=description, internal=True
    )

    # we cannot know the preimage of the swap yet
    if not is_boltz_wallet:
        assert payment.preimage

    invoice = decode(payment.bolt11)
    assert invoice.payment_hash == payment.payment_hash
    assert invoice.amount_msat == 1000000
    assert invoice.description == description

    # Internal invoices are not on fundingsource. so we should get some kind of error
    # that the invoice is not found, but we get status pending
    funding_source = get_funding_source()
    status = await funding_source.get_invoice_status(payment.payment_hash)
    assert isinstance(status, PaymentStatus)
    assert status.pending
