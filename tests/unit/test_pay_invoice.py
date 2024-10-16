import asyncio
from unittest.mock import AsyncMock

import pytest
from bolt11 import decode as bolt11_decode
from bolt11 import encode as bolt11_encode
from bolt11.types import MilliSatoshi
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import get_standalone_payment
from lnbits.core.models import Payment, PaymentState, Wallet
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.exceptions import PaymentError
from lnbits.settings import settings
from lnbits.tasks import (
    create_permanent_task,
    internal_invoice_listener,
    register_invoice_listener,
)
from lnbits.wallets.base import PaymentResponse
from lnbits.wallets.fake import FakeWallet

# external_invoice = (
#     "lnbc210n1pnsukdapp5r8hxha2kx9qyrrknlscwfayvstcx7wu5zvkwdd0hzzv83p"
#     "5d9wcsdqqcqzzsxqyz5vqsp5ra7vq6napsu5y9h4nu79a2ksjkm4rvpajpe0ce9q0"
#     "uvct22wugjs9qxpqysgqvc8uhzq4jaccvdzpmfczygnluppn74uue2uwrhpg6kegs"
#     "qpk2hmq0ksggazxfnsv3d622y9822zsxhaaj20dypzprfvcfd5e4az7w2gq9m9m6w"
# )


@pytest.mark.asyncio
async def test_invalid_bolt11(to_wallet):
    with pytest.raises(PaymentError):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request="lnbcr1123123n",
        )


@pytest.mark.asyncio
async def test_amountless_invoice(to_wallet: Wallet):
    zero_amount_invoice = (
        "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
        "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
        "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
        "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
        "6hjxepwp93cq398l3s"
    )
    with pytest.raises(PaymentError, match="Amountless invoices not supported."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=zero_amount_invoice,
        )


@pytest.mark.asyncio
async def test_payment_limit(to_wallet: Wallet):
    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=101, memo=""
    )
    with pytest.raises(PaymentError, match="Amount in invoice is too high."):

        await pay_invoice(
            wallet_id=to_wallet.id,
            max_sat=100,
            payment_request=payment_request,
        )


@pytest.mark.asyncio
async def test_pay_twice(to_wallet: Wallet):
    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=3, memo="Twice"
    )
    await pay_invoice(
        wallet_id=to_wallet.id,
        payment_request=payment_request,
    )
    with pytest.raises(PaymentError, match="Internal invoice already paid."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
        )


@pytest.mark.asyncio
async def test_pay_external_invoice_from_fake_wallet(
    to_wallet: Wallet, external_funding_source: FakeWallet
):
    external_invoice = await external_funding_source.create_invoice(21)
    assert external_invoice.payment_request
    with pytest.raises(
        PaymentError, match="Payment failed: Only internal invoices can be used!"
    ):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=external_invoice.payment_request,
        )


@pytest.mark.asyncio
async def test_amount_changed(to_wallet: Wallet):
    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=21, memo="original"
    )

    invoice = bolt11_decode(payment_request)
    invoice.amount_msat = MilliSatoshi(12000)
    payment_request = bolt11_encode(invoice)

    with pytest.raises(PaymentError, match="Invalid invoice amount."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
        )


@pytest.mark.asyncio
async def test_pay_for_extension(to_wallet: Wallet):
    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=3, memo="Allowed"
    )
    await pay_invoice(
        wallet_id=to_wallet.id, payment_request=payment_request, extra={"tag": "lnurlp"}
    )
    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=3, memo="Not Allowed"
    )
    settings.lnbits_admin_extensions = ["lnurlp"]
    with pytest.raises(
        PaymentError, match="User not authorized for extension 'lnurlp'."
    ):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
            extra={"tag": "lnurlp"},
        )


@pytest.mark.asyncio
async def test_notification_for_internal_payment(to_wallet: Wallet):
    test_name = "test_notification_for_internal_payment"

    create_permanent_task(internal_invoice_listener)
    invoice_queue: asyncio.Queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, test_name)

    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=123, memo=test_name
    )
    await pay_invoice(
        wallet_id=to_wallet.id, payment_request=payment_request, extra={"tag": "lnurlp"}
    )
    await asyncio.sleep(1)

    while True:
        payment: Payment = invoice_queue.get_nowait()  # raises if queue empty
        assert payment
        if payment.memo == test_name:
            assert payment.status == PaymentState.SUCCESS.value
            assert payment.bolt11 == payment_request
            assert payment.amount == 123_000
            break  # we found our payment, success


@pytest.mark.asyncio
async def test_pay_external_invoice_failed(
    to_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    payment_reponse = PaymentResponse(ok=False, error_message="Mock failure!")
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse),
    )

    external_invoice = await external_funding_source.create_invoice(21)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    with pytest.raises(PaymentError, match="Payment failed: Mock failure!"):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    payment = await get_standalone_payment(external_invoice.checking_id)
    assert payment
    assert payment.status == PaymentState.FAILED.value
