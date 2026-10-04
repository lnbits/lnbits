import time
from datetime import datetime, timedelta, timezone
from os import urandom
from unittest.mock import AsyncMock

import pytest
from bolt11 import Bolt11, MilliSatoshi, TagChar, Tags, encode
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_wallet, get_standalone_payment, get_wallet
from lnbits.core.crud.payments import update_payment
from lnbits.core.models import PaymentState
from lnbits.core.services import (
    cancel_hold_invoice,
    create_invoice,
    create_user_account,
    pay_invoice,
    settle_hold_invoice,
)
from lnbits.core.services.payments import update_pending_payment, update_wallet_balance
from lnbits.exceptions import InvoiceError, PaymentError
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.base import InvoiceResponse
from lnbits.wallets.fake import FakeWallet


class HoldFakeWallet(FakeWallet):
    """FakeWallet that can create hold invoices for a given payment hash."""

    def __init__(self) -> None:
        super().__init__()
        self.hold_invoice_kwargs: dict = {}
        self.settle_mock = AsyncMock(return_value=InvoiceResponse(ok=True))
        self.cancel_mock = AsyncMock(return_value=InvoiceResponse(ok=True))

    async def settle_hold_invoice(self, preimage: str) -> InvoiceResponse:
        return await self.settle_mock(preimage=preimage)

    async def cancel_hold_invoice(self, payment_hash: str) -> InvoiceResponse:
        return await self.cancel_mock(payment_hash=payment_hash)

    async def create_hold_invoice(
        self,
        amount: int,
        payment_hash: str,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        self.hold_invoice_kwargs = kwargs
        tags = Tags()
        tags.add(TagChar.description, memo or "")
        tags.add(TagChar.payment_hash, payment_hash)
        tags.add(TagChar.payment_secret, urandom(32).hex())
        if kwargs.get("expiry"):
            tags.add(TagChar.expire_time, kwargs["expiry"])
        bolt11 = Bolt11(
            currency="bc",
            amount_msat=MilliSatoshi(amount * 1000),
            date=int(time.time()),
            tags=tags,
        )
        return InvoiceResponse(
            ok=True,
            checking_id=payment_hash,
            payment_request=encode(bolt11, self.privkey),
        )


@pytest.fixture
def hold_funding_source(app, mocker: MockerFixture) -> HoldFakeWallet:
    funding_source = HoldFakeWallet()
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=funding_source,
    )
    return funding_source


async def _new_wallet(balance: int = 0):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="hold_invoice_test")
    if balance:
        await update_wallet_balance(wallet=wallet, amount=balance)
    return wallet


async def _balance_msat(wallet_id: str) -> int:
    wallet = await get_wallet(wallet_id)
    assert wallet
    return wallet.balance_msat


async def _create_paid_hold_invoice(amount: int = 1000):
    receiver = await _new_wallet()
    payer = await _new_wallet(balance=10_000)
    preimage, payment_hash = random_secret_and_hash()
    hold_invoice = await create_invoice(
        wallet_id=receiver.id,
        amount=amount,
        memo="internal hold invoice",
        payment_hash=payment_hash,
    )
    payer_balance = await _balance_msat(payer.id)
    payment = await pay_invoice(wallet_id=payer.id, payment_request=hold_invoice.bolt11)
    return receiver, payer, preimage, hold_invoice, payment, payer_balance


@pytest.mark.anyio
async def test_internal_hold_invoice_is_held(hold_funding_source: HoldFakeWallet):
    receiver, payer, _, hold_invoice, payment, payer_balance = (
        await _create_paid_hold_invoice()
    )

    assert payment.status == PaymentState.PENDING
    assert payment.checking_id == f"internal_{hold_invoice.payment_hash}"
    assert payment.preimage is None

    # the funds of the payer are locked, the receiver did not get them yet
    assert await _balance_msat(payer.id) <= payer_balance - 1000 * 1000
    assert await _balance_msat(receiver.id) == 0

    invoice = await get_standalone_payment(hold_invoice.checking_id, incoming=True)
    assert invoice
    assert invoice.status == PaymentState.PENDING
    assert invoice.extra.get("hold_invoice_accepted") is True

    # nothing is checked on the funding source while the payment is held
    invoice = await update_pending_payment(invoice)
    assert invoice.status == PaymentState.PENDING


@pytest.mark.anyio
async def test_internal_hold_invoice_settle(hold_funding_source: HoldFakeWallet):
    receiver, payer, preimage, hold_invoice, payment, payer_balance = (
        await _create_paid_hold_invoice()
    )

    with pytest.raises(InvoiceError, match="Invalid preimage."):
        await settle_hold_invoice(hold_invoice, "00" * 32)

    response = await settle_hold_invoice(hold_invoice, preimage)
    assert response.ok is True
    assert response.preimage == preimage

    # settled on this instance, the invoice on the funding source is cancelled
    hold_funding_source.settle_mock.assert_not_called()
    hold_funding_source.cancel_mock.assert_awaited_once_with(
        payment_hash=hold_invoice.payment_hash
    )

    outgoing = await get_standalone_payment(payment.checking_id)
    assert outgoing
    assert outgoing.status == PaymentState.SUCCESS
    assert outgoing.preimage == preimage

    invoice = await get_standalone_payment(hold_invoice.checking_id, incoming=True)
    assert invoice
    assert invoice.status == PaymentState.SUCCESS
    assert invoice.preimage == preimage
    assert invoice.extra.get("hold_invoice_settled") is True

    assert await _balance_msat(receiver.id) == 1000 * 1000
    assert await _balance_msat(payer.id) <= payer_balance - 1000 * 1000

    with pytest.raises(InvoiceError, match="Hold invoice is not pending."):
        await settle_hold_invoice(hold_invoice, preimage)
    with pytest.raises(InvoiceError, match="Hold invoice is not pending."):
        await cancel_hold_invoice(hold_invoice)


@pytest.mark.anyio
async def test_internal_hold_invoice_cancel(hold_funding_source: HoldFakeWallet):
    receiver, payer, preimage, hold_invoice, payment, payer_balance = (
        await _create_paid_hold_invoice()
    )

    response = await cancel_hold_invoice(hold_invoice)
    assert response.ok is True
    hold_funding_source.cancel_mock.assert_awaited_once_with(
        payment_hash=hold_invoice.payment_hash
    )

    outgoing = await get_standalone_payment(payment.checking_id)
    assert outgoing
    assert outgoing.status == PaymentState.FAILED

    invoice = await get_standalone_payment(hold_invoice.checking_id, incoming=True)
    assert invoice
    assert invoice.status == PaymentState.FAILED
    assert invoice.extra.get("hold_invoice_cancelled") is True

    # the payer is refunded
    assert await _balance_msat(payer.id) == payer_balance
    assert await _balance_msat(receiver.id) == 0

    with pytest.raises(InvoiceError, match="Hold invoice is not pending."):
        await settle_hold_invoice(hold_invoice, preimage)


@pytest.mark.anyio
async def test_internal_hold_invoice_expired(hold_funding_source: HoldFakeWallet):
    receiver, payer, _, hold_invoice, payment, payer_balance = (
        await _create_paid_hold_invoice()
    )

    invoice = await get_standalone_payment(hold_invoice.checking_id, incoming=True)
    assert invoice
    invoice.expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
    await update_payment(invoice)

    invoice = await update_pending_payment(invoice)
    assert invoice.status == PaymentState.FAILED
    assert "expired" in invoice.labels

    outgoing = await get_standalone_payment(payment.checking_id)
    assert outgoing
    assert outgoing.status == PaymentState.FAILED
    assert await _balance_msat(payer.id) == payer_balance
    assert await _balance_msat(receiver.id) == 0


@pytest.mark.anyio
async def test_internal_hold_invoice_paid_twice(hold_funding_source: HoldFakeWallet):
    *_, hold_invoice, _, _ = await _create_paid_hold_invoice()
    other_payer = await _new_wallet(balance=10_000)

    with pytest.raises(PaymentError, match="Hold invoice already paid."):
        await pay_invoice(wallet_id=other_payer.id, payment_request=hold_invoice.bolt11)


@pytest.mark.anyio
async def test_hold_invoice_expiry_is_forwarded(hold_funding_source: HoldFakeWallet):
    receiver = await _new_wallet()
    _, payment_hash = random_secret_and_hash()
    await create_invoice(
        wallet_id=receiver.id,
        amount=1000,
        memo="hold invoice expiry",
        payment_hash=payment_hash,
        expiry=7200,
    )
    assert hold_funding_source.hold_invoice_kwargs.get("expiry") == 7200
