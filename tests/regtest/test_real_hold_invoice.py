import asyncio

import pytest

from lnbits.core.models import Payment
from lnbits.core.services.payments import (
    cancel_hold_invoice,
    create_invoice,
    get_standalone_payment,
    settle_hold_invoice,
)
from lnbits.exceptions import InvoiceError
from lnbits.utils.crypto import random_secret_and_hash

from ..helpers import funding_source, is_fake
from .helpers import pay_real_invoice


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
@pytest.mark.skipif(
    funding_source.__class__.__name__ in ["LndRestWallet", "LndWallet"],
    reason="this should not raise for lnd",
)
async def test_pay_raise_unsupported(app):
    payment_hash = "0" * 32
    payment = Payment(
        checking_id=payment_hash,
        amount=1000,
        wallet_id="fake_wallet_id",
        bolt11="fake_holdinvoice",
        payment_hash=payment_hash,
        fee=0,
    )
    with pytest.raises(InvoiceError):
        await create_invoice(
            wallet_id="fake_wallet_id",
            amount=1000,
            memo="fake_holdinvoice",
            payment_hash=payment_hash,
        )
    with pytest.raises(InvoiceError):
        await settle_hold_invoice(payment, payment_hash)
    with pytest.raises(InvoiceError):
        await cancel_hold_invoice(payment)


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
@pytest.mark.skipif(
    funding_source.__class__.__name__ not in ["LndRestWallet", "LndWallet"],
    reason="this only works for lndrest",
)
async def test_cancel_real_hold_invoice(app, from_wallet):

    _, payment_hash = random_secret_and_hash()
    payment = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo="test_cancel_holdinvoice",
        payment_hash=payment_hash,
    )
    assert payment.amount == 1000 * 1000
    assert payment.memo == "test_cancel_holdinvoice"
    assert payment.status == "pending"
    assert payment.wallet_id == from_wallet.id

    payment = await cancel_hold_invoice(payment=payment)
    assert payment.ok is True

    updated_payment = await get_standalone_payment(payment_hash, incoming=True)

    assert updated_payment
    assert updated_payment.status == "failed"


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
@pytest.mark.skipif(
    funding_source.__class__.__name__ not in ["LndRestWallet", "LndWallet"],
    reason="this only works for lndrest",
)
async def test_settle_real_hold_invoice(app, from_wallet):

    preimage, payment_hash = random_secret_and_hash()
    payment = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo="test_settle_holdinvoice",
        payment_hash=payment_hash,
    )
    assert payment.amount == 1000 * 1000
    assert payment.memo == "test_settle_holdinvoice"
    assert payment.status == "pending"
    assert payment.wallet_id == from_wallet.id

    # invoice should still be open
    with pytest.raises(InvoiceError):
        await settle_hold_invoice(payment=payment, preimage=preimage)

    def pay_invoice():
        pay_real_invoice(payment.bolt11)

    async def settle():
        await asyncio.sleep(1)
        invoice_response = await settle_hold_invoice(payment=payment, preimage=preimage)
        assert invoice_response.ok is True

    coro = asyncio.to_thread(pay_invoice)
    task = asyncio.create_task(coro)
    await asyncio.gather(task, settle())

    await asyncio.sleep(1)

    updated_payment = await get_standalone_payment(payment_hash, incoming=True)

    assert updated_payment
    assert updated_payment.status == "success"
