import json
from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.models import Account, CreateInvoice
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.services.users import create_user_account
from lnbits.core.views.callback_api import (
    handle_paypal_event,
    handle_stripe_event,
)


@pytest.mark.anyio
async def test_callback_api_generic_webhook_handler_routes_providers(
    http_client: AsyncClient, mocker
):
    stripe_mock = mocker.patch(
        "lnbits.core.views.callback_api.handle_stripe_event", mocker.AsyncMock()
    )
    paypal_mock = mocker.patch(
        "lnbits.core.views.callback_api.handle_paypal_event", mocker.AsyncMock()
    )
    mocker.patch("lnbits.core.views.callback_api.check_stripe_signature")
    mocker.patch(
        "lnbits.core.views.callback_api.verify_paypal_webhook", mocker.AsyncMock()
    )

    stripe = await http_client.post(
        "/api/v1/callback/stripe",
        headers={"Stripe-Signature": "sig"},
        json={"id": "evt_1", "type": "payment_intent.succeeded"},
    )
    assert stripe.status_code == 200
    assert stripe.json()["success"] is True
    stripe_mock.assert_awaited_once()

    paypal = await http_client.post(
        "/api/v1/callback/paypal",
        json={"id": "evt_2", "event_type": "CHECKOUT.ORDER.APPROVED"},
    )
    assert paypal.status_code == 200
    assert paypal.json()["success"] is True
    paypal_mock.assert_awaited_once()

    unknown = await http_client.post("/api/v1/callback/unknown", json={"id": "evt_3"})
    assert unknown.status_code == 200
    assert unknown.json()["success"] is False


@pytest.mark.anyio
async def test_callback_api_handles_paid_events_with_real_payments(mocker):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]
    payment = await create_wallet_invoice(
        wallet.id, CreateInvoice(out=False, amount=11, memo="fiat callback")
    )

    fiat_status_mock = mocker.patch(
        "lnbits.core.views.callback_api.check_fiat_status", mocker.AsyncMock()
    )

    await handle_stripe_event(
        {
            "id": "evt_stripe",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "object": "payment_intent",
                    "metadata": {"payment_hash": payment.payment_hash},
                }
            },
        }
    )
    await handle_paypal_event(
        {
            "id": "evt_paypal",
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource": {
                "purchase_units": [{"invoice_id": payment.payment_hash}],
            },
        }
    )
    await handle_stripe_event({"id": "evt_unhandled", "type": "customer.created"})

    assert fiat_status_mock.await_count == 2


@pytest.mark.anyio
async def test_callback_api_handles_subscription_flows_and_validation(mocker):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]
    payment = await create_wallet_invoice(
        wallet.id, CreateInvoice(out=False, amount=15, memo="subscription")
    )

    create_fiat_invoice_mock = mocker.patch(
        "lnbits.core.views.callback_api.create_fiat_invoice",
        mocker.AsyncMock(return_value=payment),
    )
    fiat_status_mock = mocker.patch(
        "lnbits.core.views.callback_api.check_fiat_status", mocker.AsyncMock()
    )

    await handle_stripe_event(
        {
            "id": "evt_invoice_paid",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "invoice_1",
                    "currency": "usd",
                    "amount_paid": 500,
                    "hosted_invoice_url": "https://stripe.example/invoice",
                    "customer_email": "alice@example.com",
                    "lines": {"data": [{"description": "Gold Plan"}]},
                    "parent": {
                        "type": "subscription_details",
                        "subscription_details": {
                            "metadata": {
                                "alan_action": "subscription",
                                "wallet_id": wallet.id,
                                "tag": "gold",
                                "memo": "Monthly Gold",
                                "extra": json.dumps({"plan": "gold"}),
                            }
                        },
                    },
                }
            },
        }
    )
    create_fiat_invoice_mock.assert_awaited()
    fiat_status_mock.assert_awaited()

    await handle_paypal_event(
        {
            "id": "evt_sale_completed",
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "id": "sale_1",
                "billing_agreement_id": "agreement_1",
                "amount": {"currency": "USD", "total": "7.50"},
                "custom_id": json.dumps(
                    [wallet.id, "vip", "subscription_1", "link-1", "VIP Plan"]
                ),
            },
        }
    )
    assert create_fiat_invoice_mock.await_count == 2

    with pytest.raises(ValueError, match="PayPal subscription event missing custom metadata."):
        await handle_paypal_event(
            {
                "id": "evt_bad_sale",
                "event_type": "PAYMENT.SALE.COMPLETED",
                "resource": {"amount": {"currency": "USD", "total": "5.00"}},
            }
        )
