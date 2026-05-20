import json
from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.models import Account, CreateInvoice, Payment
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.services.users import create_user_account
from lnbits.core.views.callback_api import (
    handle_paypal_event,
    handle_revolut_event,
    handle_square_event,
    handle_stripe_event,
)
from lnbits.fiat.revolut import RevolutWallet
from lnbits.fiat.square import SquareWallet
from lnbits.settings import Settings


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
    square_mock = mocker.patch(
        "lnbits.core.views.callback_api.handle_square_event", mocker.AsyncMock()
    )
    revolut_mock = mocker.patch(
        "lnbits.core.views.callback_api.handle_revolut_event", mocker.AsyncMock()
    )
    mocker.patch("lnbits.core.views.callback_api.check_stripe_signature")
    mocker.patch("lnbits.core.views.callback_api.check_square_signature")
    mocker.patch("lnbits.core.views.callback_api.check_revolut_signature")
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

    square = await http_client.post(
        "/api/v1/callback/square",
        headers={"x-square-hmacsha256-signature": "sig"},
        json={"event_id": "evt_3", "type": "payment.updated"},
    )
    assert square.status_code == 200
    assert square.json()["success"] is True
    square_mock.assert_awaited_once()

    revolut = await http_client.post(
        "/api/v1/callback/revolut",
        headers={
            "Revolut-Signature": "sig",
            "Revolut-Request-Timestamp": "1700000000",
        },
        json={"event": "ORDER_COMPLETED", "order_id": "order_1"},
    )
    assert revolut.status_code == 200
    assert revolut.json()["success"] is True
    revolut_mock.assert_awaited_once()

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
async def test_callback_api_handles_square_paid_events(mocker):
    payment = mocker.Mock()
    get_payment = mocker.patch(
        "lnbits.core.views.callback_api.get_standalone_payment",
        mocker.AsyncMock(return_value=payment),
    )
    fiat_status_mock = mocker.patch(
        "lnbits.core.views.callback_api.check_fiat_status", mocker.AsyncMock()
    )

    await handle_square_event(
        {
            "event_id": "evt_square",
            "type": "payment.updated",
            "data": {
                "object": {
                    "payment": {
                        "id": "payment_1",
                        "order_id": "order_1",
                        "status": "COMPLETED",
                    }
                }
            },
        }
    )

    get_payment.assert_awaited_once_with("fiat_square_order_order_1")
    fiat_status_mock.assert_awaited_once_with(payment)


@pytest.mark.anyio
async def test_callback_api_handles_revolut_paid_events(mocker):
    payment = mocker.Mock()
    get_payment = mocker.patch(
        "lnbits.core.views.callback_api.get_standalone_payment",
        mocker.AsyncMock(return_value=payment),
    )
    fiat_status_mock = mocker.patch(
        "lnbits.core.views.callback_api.check_fiat_status", mocker.AsyncMock()
    )

    await handle_revolut_event(
        {
            "event": "ORDER_COMPLETED",
            "order_id": "order_1",
        }
    )

    get_payment.assert_awaited_once_with("fiat_revolut_order_order_1")
    fiat_status_mock.assert_awaited_once_with(payment)


@pytest.mark.anyio
async def test_callback_api_handles_revolut_subscription_event(
    mocker, settings: Settings
):
    wallet_id = "wallet_1"
    payment = mocker.Mock()
    payment.extra = {}
    payment.msat = 925_000

    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"
    revolut_provider = RevolutWallet()
    mocker.patch.object(
        revolut_provider,
        "get_subscription",
        return_value={
            "id": "SUBSCRIPTION_1",
            "current_cycle_id": "CYCLE_1",
            "external_reference": json.dumps(
                {
                    "wallet_id": wallet_id,
                    "tag": "members",
                    "subscription_request_id": "request_1",
                    "extra": {"link": "link-1", "customer_id": "customer_1"},
                    "memo": "Revolut Members",
                }
            ),
        },
    )
    mocker.patch.object(
        revolut_provider,
        "get_subscription_cycle",
        return_value={"id": "CYCLE_1", "order_id": "ORDER_SUB_1"},
    )
    mocker.patch.object(
        revolut_provider,
        "get_order",
        return_value={
            "id": "ORDER_SUB_1",
            "amount": 925,
            "currency": "USD",
            "checkout_url": "https://checkout.revolut.com/payment-link/sub_1",
        },
    )
    mocker.patch(
        "lnbits.core.views.callback_api.get_fiat_provider",
        mocker.AsyncMock(return_value=revolut_provider),
    )
    mocker.patch(
        "lnbits.core.views.callback_api.get_standalone_payment",
        mocker.AsyncMock(side_effect=[None]),
    )
    create_wallet_invoice_mock = mocker.patch(
        "lnbits.core.views.callback_api.create_wallet_invoice",
        mocker.AsyncMock(return_value=payment),
    )
    mocker.patch("lnbits.core.views.callback_api.service_fee_fiat", return_value=2)
    update_payment_mock = mocker.patch(
        "lnbits.core.views.callback_api.update_payment", mocker.AsyncMock()
    )
    fiat_status_mock = mocker.patch(
        "lnbits.core.views.callback_api.check_fiat_status", mocker.AsyncMock()
    )

    await handle_revolut_event(
        {
            "event": "SUBSCRIPTION_INITIATED",
            "subscription_id": "SUBSCRIPTION_1",
        }
    )

    assert create_wallet_invoice_mock.await_count == 1
    called_wallet_id, invoice = create_wallet_invoice_mock.await_args.args
    assert called_wallet_id == "wallet_1"
    assert invoice.amount == 9.25
    assert invoice.memo == "Revolut Members"
    assert invoice.external_id == "SUBSCRIPTION_1"
    assert invoice.internal is True
    assert invoice.extra["fiat_method"] == "subscription"
    assert invoice.extra["subscription"]["checking_id"] == "order_ORDER_SUB_1"
    assert payment.fiat_provider == "revolut"
    assert payment.fee == -2
    assert payment.extra["fiat_checking_id"] == "order_ORDER_SUB_1"
    assert payment.checking_id == "fiat_revolut_order_ORDER_SUB_1"
    update_payment_mock.assert_awaited_once_with(
        payment, "fiat_revolut_order_ORDER_SUB_1"
    )
    fiat_status_mock.assert_awaited_once_with(payment)


@pytest.mark.anyio
async def test_callback_api_handles_subscription_flows_and_validation(
    mocker, settings: Settings
):
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

    await handle_square_event(
        {
            "event_id": "evt_square_subscription",
            "type": "payment.updated",
            "data": {
                "object": {
                    "payment": {
                        "id": "PAYMENT_SUB_1",
                        "order_id": "ORDER_SUB_1",
                        "status": "COMPLETED",
                        "amount_money": {"amount": 925, "currency": "USD"},
                        "note": json.dumps(
                            [
                                wallet.id,
                                "members",
                                "subscription_square_1",
                                "link-1",
                                "Square Members",
                            ]
                        ),
                    }
                }
            },
        }
    )
    assert create_fiat_invoice_mock.await_count == 3
    square_call = create_fiat_invoice_mock.await_args.kwargs
    assert square_call["wallet_id"] == wallet.id
    square_invoice = square_call["invoice_data"]
    assert square_invoice.fiat_provider == "square"
    assert square_invoice.amount == 9.25
    assert square_invoice.memo == "Square Members"
    assert square_invoice.extra["fiat_method"] == "subscription"
    assert square_invoice.extra["tag"] == "members"
    assert (
        square_invoice.extra["subscription"]["checking_id"] == "payment_PAYMENT_SUB_1"
    )

    payment.extra = {
        "subscription_request_id": "subscription_square_1",
        "tag": "members",
        "link": "link-1",
    }
    payment.external_id = "SUBSCRIPTION_1"
    payment.memo = "Square Members"
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"
    square_provider = SquareWallet()
    mocker.patch.object(
        square_provider,
        "get_payment_for_order",
        return_value={
            "id": "PAYMENT_SUB_2",
            "status": "COMPLETED",
            "amount_money": {"amount": 925, "currency": "USD"},
        },
    )
    mocker.patch(
        "lnbits.core.views.callback_api.get_fiat_provider",
        mocker.AsyncMock(return_value=square_provider),
    )
    mocker.patch(
        "lnbits.core.views.callback_api.get_payments",
        mocker.AsyncMock(return_value=[payment]),
    )

    await handle_square_event(
        {
            "event_id": "evt_square_invoice",
            "type": "invoice.payment_made",
            "data": {
                "object": {
                    "invoice": {
                        "order_id": "ORDER_SUB_2",
                        "subscription_id": "SUBSCRIPTION_1",
                        "public_url": "https://square.example/invoice",
                    }
                }
            },
        }
    )
    assert create_fiat_invoice_mock.await_count == 4
    square_invoice_call = create_fiat_invoice_mock.await_args.kwargs
    square_invoice = square_invoice_call["invoice_data"]
    assert square_invoice.external_id == "SUBSCRIPTION_1"
    assert "square_subscription_id" not in square_invoice.extra
    assert (
        square_invoice.extra["subscription"]["payment_request"]
        == "https://square.example/invoice"
    )

    with pytest.raises(
        ValueError, match="PayPal subscription event missing custom metadata."
    ):
        await handle_paypal_event(
            {
                "id": "evt_bad_sale",
                "event_type": "PAYMENT.SALE.COMPLETED",
                "resource": {"amount": {"currency": "USD", "total": "5.00"}},
            }
        )


@pytest.mark.anyio
async def test_square_invoice_payment_updates_existing_subscription_external_id(
    settings: Settings, mocker
):
    payment = Payment(
        checking_id="fiat_square_payment_PAYMENT_SUB_1",
        payment_hash="hash_square_subscription",
        wallet_id="wallet_1",
        amount=925000,
        fee=0,
        bolt11="lnbc1square",
        fiat_provider="square",
        extra={
            "subscription_request_id": "subscription_square_1",
            "tag": "members",
            "link": "link-1",
        },
        memo="Square Members",
    )
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"
    square_provider = SquareWallet()
    mocker.patch.object(
        square_provider,
        "get_payment_for_order",
        return_value={
            "id": "PAYMENT_SUB_1",
            "status": "COMPLETED",
            "amount_money": {"amount": 925, "currency": "USD"},
        },
    )
    mocker.patch(
        "lnbits.core.views.callback_api.get_fiat_provider",
        mocker.AsyncMock(return_value=square_provider),
    )
    get_standalone_payment_mock = mocker.patch(
        "lnbits.core.views.callback_api.get_standalone_payment",
        mocker.AsyncMock(return_value=payment),
    )
    update_payment_mock = mocker.patch(
        "lnbits.core.views.callback_api.update_payment",
        mocker.AsyncMock(),
    )
    get_payments_mock = mocker.patch(
        "lnbits.core.views.callback_api.get_payments",
        mocker.AsyncMock(return_value=[]),
    )
    create_fiat_invoice_mock = mocker.patch(
        "lnbits.core.views.callback_api.create_fiat_invoice",
        mocker.AsyncMock(),
    )
    fiat_status_mock = mocker.patch(
        "lnbits.core.views.callback_api.check_fiat_status", mocker.AsyncMock()
    )

    await handle_square_event(
        {
            "event_id": "evt_square_invoice",
            "type": "invoice.payment_made",
            "data": {
                "object": {
                    "invoice": {
                        "order_id": "ORDER_SUB_1",
                        "subscription_id": "SUBSCRIPTION_1",
                    }
                }
            },
        }
    )

    get_standalone_payment_mock.assert_awaited_with("fiat_square_payment_PAYMENT_SUB_1")
    assert payment.external_id == "SUBSCRIPTION_1"
    update_payment_mock.assert_awaited_once_with(payment)
    fiat_status_mock.assert_awaited_once_with(payment)
    get_payments_mock.assert_not_awaited()
    create_fiat_invoice_mock.assert_not_awaited()
