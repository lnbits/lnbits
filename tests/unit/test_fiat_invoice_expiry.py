from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud.payments import get_standalone_payment, update_payment
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models.payments import CreateInvoice, Payment, PaymentState
from lnbits.core.services import payments
from lnbits.core.services.payments import check_pending_payments
from lnbits.core.services.users import create_user_account
from lnbits.core.views.callback_api import handle_stripe_event
from lnbits.fiat.base import (
    FiatInvoiceResponse,
    FiatPaymentPendingStatus,
    FiatPaymentSuccessStatus,
)
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_fiat_invoice_defaults_to_24h_expiry(
    app, settings: Settings, mocker: MockerFixture
):
    """A Stripe Checkout session is payable for 24 h. The buyer pays at minute 61,
    after the pending sweep has run: the invoice must still be pending, and the
    wallet credited when checkout.session.completed arrives."""
    wallet_id, session_id = await _stripe_setup(settings, mocker)
    payment = await payments.create_fiat_invoice(
        wallet_id, CreateInvoice(unit="USD", amount=5.0, fiat_provider="stripe")
    )
    assert payment.status == PaymentState.PENDING
    assert 24 * 3600 - 100 < _seconds_left(payment) <= 24 * 3600

    # 61 minutes later: past the 1 h Lightning expiry, Stripe not paid yet.
    assert payment.expiry is not None
    payment.expiry -= timedelta(minutes=61)
    await update_payment(payment)
    mocker.patch(
        "lnbits.fiat.StripeWallet.get_invoice_status",
        AsyncMock(return_value=FiatPaymentPendingStatus()),
    )
    await check_pending_payments()
    after_sweep = await get_standalone_payment(payment.checking_id)
    assert after_sweep is not None
    assert after_sweep.status == PaymentState.PENDING

    # The buyer pays; Stripe sends checkout.session.completed.
    mocker.patch(
        "lnbits.fiat.StripeWallet.get_invoice_status",
        AsyncMock(return_value=FiatPaymentSuccessStatus()),
    )
    await handle_stripe_event(_checkout_completed(session_id, payment.payment_hash))

    final = await get_standalone_payment(payment.checking_id)
    credited = await get_wallet(wallet_id)
    assert final is not None and credited is not None
    assert final.status == PaymentState.SUCCESS
    assert credited.balance_msat > 0


@pytest.mark.anyio
async def test_fiat_invoice_keeps_explicit_expiry_and_fails_after_it(
    app, settings: Settings, mocker: MockerFixture
):
    """An expiry passed by the caller is kept, and an unpaid fiat invoice is still
    failed by the sweep once it has expired."""
    wallet_id, _ = await _stripe_setup(settings, mocker)
    payment = await payments.create_fiat_invoice(
        wallet_id,
        CreateInvoice(unit="USD", amount=5.0, fiat_provider="stripe", expiry=600),
    )
    assert 500 < _seconds_left(payment) <= 600

    payment.expiry = datetime.now(timezone.utc) - timedelta(minutes=1)
    await update_payment(payment)
    await check_pending_payments()

    expired = await get_standalone_payment(payment.checking_id)
    assert expired is not None
    assert expired.status == PaymentState.FAILED
    assert "expired" in expired.labels


async def _stripe_setup(settings: Settings, mocker: MockerFixture) -> tuple[str, str]:
    settings.stripe_enabled = True
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    settings.stripe_limits.service_min_amount_sats = 0
    settings.stripe_limits.service_max_amount_sats = 0
    settings.stripe_limits.service_faucet_wallet_id = None

    user = await create_user_account()
    session_id = f"cs_test_{urlsafe_short_hash()}"
    mocker.patch(
        "lnbits.fiat.StripeWallet.create_invoice",
        AsyncMock(
            return_value=FiatInvoiceResponse(
                ok=True,
                checking_id=session_id,
                payment_request=f"https://checkout.stripe.com/c/pay/{session_id}",
            )
        ),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),
    )
    return user.wallets[0].id, session_id


def _seconds_left(payment: Payment) -> float:
    assert payment.expiry is not None
    # .timestamp() reads a naive datetime as local time, the way it was created
    return payment.expiry.timestamp() - datetime.now(timezone.utc).timestamp()


def _checkout_completed(session_id: str, payment_hash: str) -> dict:
    return {
        "id": "evt_checkout_completed",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "object": "checkout.session",
                "id": session_id,
                "payment_status": "paid",
                "metadata": {"payment_hash": payment_hash, "alan_action": "invoice"},
            }
        },
    }
