from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud.payments import get_standalone_payment, update_payment
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models.payments import CreateInvoice, PaymentState
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
async def test_stripe_payment_after_lightning_expiry_is_credited(
    app, settings: Settings, mocker: MockerFixture
):
    """A Stripe Checkout session is open for 24 h, the internal invoice behind it
    expires after `lightning_invoice_expiry` (1 h). The buyer pays at minute 61,
    after the periodic pending sweep has run once."""
    settings.stripe_enabled = True
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    settings.stripe_limits.service_min_amount_sats = 0
    settings.stripe_limits.service_max_amount_sats = 0
    settings.stripe_limits.service_faucet_wallet_id = None

    user = await create_user_account()
    wallet = user.wallets[0]

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
    payment = await payments.create_fiat_invoice(
        wallet.id, CreateInvoice(unit="USD", amount=5.0, fiat_provider="stripe")
    )
    assert payment.status == PaymentState.PENDING
    assert payment.expiry is not None
    # .timestamp() reads a naive datetime as local time, the way it was created
    expiry_seconds = payment.expiry.timestamp() - datetime.now(timezone.utc).timestamp()
    assert 3500 < expiry_seconds <= 3600  # lightning_invoice_expiry, not Stripe's 24 h

    # One hour later: the Lightning expiry has passed, the Stripe session is still open
    # (Stripe has not been paid yet).
    payment.expiry = datetime.now(timezone.utc) - timedelta(minutes=1)
    await update_payment(payment)
    stripe_status = mocker.patch(
        "lnbits.fiat.StripeWallet.get_invoice_status",
        AsyncMock(return_value=FiatPaymentPendingStatus()),
    )

    await check_pending_payments()  # runs every 30 min in production

    after_sweep = await get_standalone_payment(payment.checking_id)
    assert after_sweep is not None
    print(
        f"\n[sweep] status={after_sweep.status} "
        f"stripe_asked={stripe_status.await_count}"
    )

    # Minute 61: the buyer pays; Stripe sends checkout.session.completed.
    stripe_status.return_value = FiatPaymentSuccessStatus()
    await handle_stripe_event(
        {
            "id": "evt_checkout_completed",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "object": "checkout.session",
                    "id": session_id,
                    "payment_status": "paid",
                    "metadata": {
                        "payment_hash": payment.payment_hash,
                        "alan_action": "invoice",
                    },
                }
            },
        }
    )

    final = await get_standalone_payment(payment.checking_id)
    credited = await get_wallet(wallet.id)
    assert final is not None and credited is not None
    print(
        f"[webhook] status={final.status} balance_msat={credited.balance_msat} "
        f"(invoice {payment.amount} msat, fee {payment.fee})"
    )

    # Stripe took the money, so the wallet must be credited.
    assert after_sweep.status == PaymentState.PENDING
    assert final.status == PaymentState.SUCCESS
    assert credited.balance_msat > 0
