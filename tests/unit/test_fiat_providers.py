import hashlib
import hmac
import json
import time
from base64 import b64encode
from unittest.mock import AsyncMock

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud.payments import get_payments
from lnbits.core.crud.users import get_user
from lnbits.core.crud.wallets import create_wallet
from lnbits.core.models.payments import CreateInvoice, Payment, PaymentState
from lnbits.core.models.users import User
from lnbits.core.models.wallets import Wallet
from lnbits.core.services import check_payment_status, payments
from lnbits.core.services.fiat_providers import (
    check_fiat_status,
    check_revolut_signature,
    check_square_signature,
    check_stripe_signature,
    handle_fiat_payment_confirmation,
    verify_paypal_webhook,
)
from lnbits.core.services.fiat_providers import (
    test_connection as fiat_provider_connection,
)
from lnbits.core.services.users import create_user_account
from lnbits.fiat.base import (
    FiatInvoiceResponse,
    FiatPaymentStatus,
    FiatStatusResponse,
    FiatSubscriptionPaymentOptions,
)
from lnbits.fiat.revolut import REVOLUT_WEBHOOK_EVENTS, RevolutWallet
from lnbits.fiat.square import SquareWallet
from lnbits.settings import Settings
from tests.helpers import get_random_string


class MockHTTPResponse:
    def __init__(self, json_data=None, error: Exception | None = None):
        self._json_data = json_data or {}
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._json_data


class MockHTTPClient:
    def __init__(self, responses: list[MockHTTPResponse]):
        self._responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, path: str, **kwargs):
        self.calls.append((path, kwargs))
        return self._responses.pop(0)

    async def get(self, path: str, **kwargs):
        self.calls.append((path, kwargs))
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def fiat_provider_test_settings(settings: Settings):
    original_lnbits_running = settings.lnbits_running
    original_allowed_currencies = settings.lnbits_allowed_currencies
    original_paypal_enabled = settings.paypal_enabled
    original_square_enabled = settings.square_enabled
    original_square_api_endpoint = settings.square_api_endpoint
    original_square_access_token = settings.square_access_token
    original_square_location_id = settings.square_location_id
    original_square_api_version = settings.square_api_version
    original_square_payment_success_url = settings.square_payment_success_url
    original_square_payment_webhook_url = settings.square_payment_webhook_url
    original_square_webhook_signature_key = settings.square_webhook_signature_key
    original_square_limits = settings.square_limits.copy(deep=True)
    original_revolut_enabled = settings.revolut_enabled
    original_revolut_api_endpoint = settings.revolut_api_endpoint
    original_revolut_api_secret_key = settings.revolut_api_secret_key
    original_revolut_api_version = settings.revolut_api_version
    original_revolut_payment_success_url = settings.revolut_payment_success_url
    original_revolut_payment_webhook_url = settings.revolut_payment_webhook_url
    original_revolut_webhook_signing_secret = settings.revolut_webhook_signing_secret
    original_revolut_limits = settings.revolut_limits.copy(deep=True)
    settings.lnbits_allowed_currencies = []
    settings.paypal_enabled = False
    settings.square_enabled = False
    settings.revolut_enabled = False
    yield
    settings.lnbits_running = original_lnbits_running
    settings.lnbits_allowed_currencies = original_allowed_currencies
    settings.paypal_enabled = original_paypal_enabled
    settings.square_enabled = original_square_enabled
    settings.square_api_endpoint = original_square_api_endpoint
    settings.square_access_token = original_square_access_token
    settings.square_location_id = original_square_location_id
    settings.square_api_version = original_square_api_version
    settings.square_payment_success_url = original_square_payment_success_url
    settings.square_payment_webhook_url = original_square_payment_webhook_url
    settings.square_webhook_signature_key = original_square_webhook_signature_key
    settings.square_limits = original_square_limits
    settings.revolut_enabled = original_revolut_enabled
    settings.revolut_api_endpoint = original_revolut_api_endpoint
    settings.revolut_api_secret_key = original_revolut_api_secret_key
    settings.revolut_api_version = original_revolut_api_version
    settings.revolut_payment_success_url = original_revolut_payment_success_url
    settings.revolut_payment_webhook_url = original_revolut_payment_webhook_url
    settings.revolut_webhook_signing_secret = original_revolut_webhook_signing_secret
    settings.revolut_limits = original_revolut_limits


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_missing_provider():
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider=None
    )
    with pytest.raises(ValueError, match="Fiat provider is required"):
        await payments.create_fiat_invoice("wallet_id", invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_provider_not_enabled(settings: Settings):
    settings.stripe_enabled = False
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="notarealprovider"
    )
    with pytest.raises(
        ValueError, match="Fiat provider 'notarealprovider' is not enabled"
    ):
        await payments.create_fiat_invoice("wallet_id", invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_with_sat_unit(settings: Settings):
    settings.stripe_enabled = True
    invoice_data = CreateInvoice(
        unit="sat", amount=1.0, memo="Test", fiat_provider="stripe"
    )
    with pytest.raises(ValueError, match="Fiat provider cannot be used with satoshis"):
        await payments.create_fiat_invoice("wallet_id", invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_allowed_users(
    to_user: User, settings: Settings
):

    settings.stripe_enabled = False
    settings.stripe_limits.allowed_users = []
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == []

    settings.stripe_enabled = True
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == ["stripe"]

    settings.stripe_limits.allowed_users = ["some_other_user_id"]
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == []

    settings.stripe_limits.allowed_users.append(to_user.id)
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == ["stripe"]

    settings.stripe_enabled = False
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == []

    settings.square_enabled = True
    settings.square_limits.allowed_users = []
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == ["square"]

    settings.square_limits.allowed_users = ["some_other_user_id"]
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == []

    settings.square_limits.allowed_users.append(to_user.id)
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == ["square"]

    settings.square_enabled = False
    settings.revolut_enabled = True
    settings.revolut_limits.allowed_users = []
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == ["revolut"]

    settings.revolut_limits.allowed_users = ["some_other_user_id"]
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == []

    settings.revolut_limits.allowed_users.append(to_user.id)
    user = await get_user(to_user.id)
    assert user
    assert user.fiat_providers == ["revolut"]


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_fiat_limits_fail(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):

    settings.stripe_enabled = True
    settings.stripe_limits.service_min_amount_sats = 0
    settings.stripe_limits.service_max_amount_sats = 105
    settings.stripe_limits.service_faucet_wallet_id = None
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="stripe"
    )

    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),  # 1 BTC = 100 000 USD, so 1 USD = 1000 sats
    )
    with pytest.raises(ValueError, match="Maximum amount is 105 sats for 'stripe'."):
        await payments.create_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_min_amount_sats = 1001
    settings.stripe_limits.service_max_amount_sats = 10000

    with pytest.raises(ValueError, match="Minimum amount is 1001 sats for 'stripe'."):
        await payments.create_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_min_amount_sats = 10
    settings.stripe_limits.service_max_amount_sats = 10000
    settings.stripe_limits.service_max_fee_sats = 100

    with pytest.raises(
        ValueError, match="Fiat provider 'stripe' service fee wallet missing."
    ):
        await payments.create_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_fee_wallet_id = "not_a_real_wallet_id"

    with pytest.raises(
        ValueError, match="Fiat provider 'stripe' service fee wallet not found."
    ):
        await payments.create_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_fee_wallet_id = to_wallet.id
    settings.stripe_limits.service_faucet_wallet_id = "not_a_real_wallet_id"

    with pytest.raises(
        ValueError, match="Fiat provider 'stripe' faucet wallet not found."
    ):
        await payments.create_fiat_invoice(to_wallet.id, invoice_data)

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    settings.stripe_limits.service_faucet_wallet_id = wallet.id

    with pytest.raises(
        ValueError, match="The amount exceeds the 'stripe'faucet wallet balance."
    ):
        await payments.create_fiat_invoice(to_wallet.id, invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_provider_fails(
    settings: Settings, mocker: MockerFixture
):
    settings.stripe_enabled = True
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    invoice_data = CreateInvoice(
        unit="USD", amount=2.0, memo="Test", fiat_provider="stripe"
    )

    fiat_mock_response = FiatInvoiceResponse(
        ok=False,
        error_message="Failed to create invoice",
    )

    mocker.patch(
        "lnbits.fiat.StripeWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),  # 1 BTC = 100 000 USD, so 1 USD = 1000 sats
    )

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    with pytest.raises(ValueError, match="Cannot create payment request for 'stripe'."):
        await payments.create_fiat_invoice(wallet.id, invoice_data)

    wallet_payments = await get_payments(wallet_id=wallet.id)
    assert len(wallet_payments) == 1
    assert wallet_payments[0].status == PaymentState.FAILED
    assert wallet_payments[0].amount == 2000000
    assert wallet_payments[0].fee == 0


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_success(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.stripe_enabled = True
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    settings.stripe_limits.service_min_amount_sats = 0
    settings.stripe_limits.service_max_amount_sats = 0
    settings.stripe_limits.service_faucet_wallet_id = None

    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="stripe"
    )
    fiat_mock_response = FiatInvoiceResponse(
        ok=True,
        checking_id=f"session_123_{get_random_string(10)}",
        payment_request="https://stripe.com/pay/session_123",
    )

    mocker.patch(
        "lnbits.fiat.StripeWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),  # 1 BTC = 100 000 USD, so 1 USD = 1000 sats
    )
    payment = await payments.create_fiat_invoice(to_wallet.id, invoice_data)
    assert payment.status == PaymentState.PENDING
    assert payment.amount == 1000_000
    assert payment.fiat_provider == "stripe"
    assert payment.extra.get("fiat_checking_id") == fiat_mock_response.checking_id
    assert (
        payment.extra.get("fiat_payment_request")
        == "https://stripe.com/pay/session_123"
    )
    assert payment.checking_id.startswith("fiat_stripe_")
    assert payment.fee <= 0

    status = await check_payment_status(payment)
    assert status.success is False
    assert status.pending is True

    fiat_mock_status = FiatPaymentStatus(paid=True, fee=123)
    mocker.patch(
        "lnbits.fiat.StripeWallet.get_invoice_status",
        AsyncMock(return_value=fiat_mock_status),
    )
    status = await check_payment_status(payment)
    assert status.paid is True
    assert status.success is True


@pytest.mark.anyio
async def test_create_wallet_square_fiat_invoice_success(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.square_enabled = True
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_limits.service_min_amount_sats = 0
    settings.square_limits.service_max_amount_sats = 0
    settings.square_limits.service_faucet_wallet_id = None

    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="square"
    )
    fiat_mock_response = FiatInvoiceResponse(
        ok=True,
        checking_id="order_123",
        payment_request="https://square.link/u/session_123",
    )

    mocker.patch(
        "lnbits.fiat.SquareWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),
    )
    payment = await payments.create_fiat_invoice(to_wallet.id, invoice_data)
    assert payment.status == PaymentState.PENDING
    assert payment.fiat_provider == "square"
    assert payment.extra.get("fiat_checking_id") == fiat_mock_response.checking_id
    assert payment.checking_id.startswith("fiat_square_order_123")


@pytest.mark.anyio
async def test_square_wallet_create_invoice(settings: Settings):
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"
    settings.square_payment_success_url = "https://lnbits.example/success"

    wallet = SquareWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "payment_link": {
                        "order_id": "ORDER123",
                        "url": "https://square.link/u/abc123",
                    }
                }
            )
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    response = await wallet.create_invoice(
        amount=1.23,
        payment_hash="hash123",
        currency="USD",
        memo="LNbits Square invoice",
        extra={"checkout": {"metadata": {"source": "test"}}},
    )

    assert response.ok is True
    assert response.checking_id == "order_ORDER123"
    assert response.payment_request == "https://square.link/u/abc123"
    assert client.calls[0][0] == "/v2/online-checkout/payment-links"
    payload = client.calls[0][1]["json"]
    assert payload["idempotency_key"] == "hash123"
    assert payload["order"]["location_id"] == "LOC123"
    assert payload["order"]["metadata"]["payment_hash"] == "hash123"
    assert payload["order"]["metadata"]["alan_action"] == "invoice"
    assert payload["order"]["metadata"]["source"] == "test"
    assert payload["order"]["line_items"][0]["base_price_money"]["amount"] == 123


@pytest.mark.anyio
async def test_square_wallet_create_subscription(settings: Settings):
    settings.lnbits_running = False
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"
    settings.square_payment_success_url = "https://lnbits.example/success"

    wallet = SquareWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "object": {
                        "type": "SUBSCRIPTION_PLAN_VARIATION",
                        "id": "PLAN_VARIATION_123",
                        "subscription_plan_variation_data": {
                            "phases": [
                                {
                                    "ordinal": 0,
                                    "pricing": {
                                        "type": "STATIC",
                                        "price_money": {
                                            "amount": 1500,
                                            "currency": "USD",
                                        },
                                    },
                                }
                            ]
                        },
                    }
                }
            ),
            MockHTTPResponse(
                json_data={
                    "payment_link": {
                        "id": "plink_123",
                        "url": "https://square.link/u/sub_123",
                    }
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    payment_options = FiatSubscriptionPaymentOptions(
        wallet_id="wallet_1",
        memo="Monthly Gold",
        tag="gold",
        extra={"link": "link-1"},
        success_url="https://lnbits.example/subscription-success",
    )

    response = await wallet.create_subscription(
        "PLAN_VARIATION_123", 1, payment_options
    )

    assert response.ok is True
    assert response.checkout_session_url == "https://square.link/u/sub_123"
    assert response.subscription_request_id is not None
    assert client.calls[0][0] == "/v2/catalog/object/PLAN_VARIATION_123"
    assert client.calls[1][0] == "/v2/online-checkout/payment-links"
    payload = client.calls[1][1]["json"]
    assert payload["idempotency_key"] == response.subscription_request_id
    assert payload["quick_pay"]["location_id"] == "LOC123"
    assert payload["quick_pay"]["price_money"] == {"amount": 1500, "currency": "USD"}
    assert payload["checkout_options"] == {
        "redirect_url": "https://lnbits.example/subscription-success",
        "subscription_plan_id": "PLAN_VARIATION_123",
    }
    metadata = json.loads(payload["payment_note"])
    assert metadata[:3] == ["wallet_1", "gold", response.subscription_request_id]
    assert metadata[3:] == ["link-1", "Monthly Gold"]


@pytest.mark.anyio
async def test_square_wallet_create_subscription_from_plan_id(settings: Settings):
    settings.lnbits_running = False
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"
    settings.square_payment_success_url = "https://lnbits.example/success"

    wallet = SquareWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "object": {
                        "type": "SUBSCRIPTION_PLAN",
                        "id": "PLAN123",
                        "subscription_plan_data": {
                            "name": "LNbits Test Weekly Personal Plan",
                            "subscription_plan_variations": [
                                {
                                    "type": "SUBSCRIPTION_PLAN_VARIATION",
                                    "id": "PLAN_VARIATION_123",
                                    "subscription_plan_variation_data": {
                                        "name": "LNbits Test Weekly Personal Plan",
                                        "phases": [
                                            {
                                                "uid": "PHASE123",
                                                "cadence": "WEEKLY",
                                                "ordinal": 0,
                                                "pricing": {"type": "RELATIVE"},
                                            }
                                        ],
                                        "subscription_plan_id": "PLAN123",
                                    },
                                }
                            ],
                            "eligible_item_ids": ["ITEM123"],
                            "all_items": False,
                        },
                    }
                }
            ),
            MockHTTPResponse(
                json_data={
                    "object": {
                        "type": "ITEM",
                        "id": "ITEM123",
                        "item_data": {
                            "name": "LNbits Test Weekly Personal Plan",
                            "variations": [
                                {
                                    "type": "ITEM_VARIATION",
                                    "id": "ITEM_VARIATION_123",
                                    "item_variation_data": {
                                        "item_id": "ITEM123",
                                        "name": "Regular",
                                        "pricing_type": "FIXED_PRICING",
                                        "price_money": {
                                            "amount": 1500,
                                            "currency": "USD",
                                        },
                                    },
                                }
                            ],
                        },
                    }
                }
            ),
            MockHTTPResponse(
                json_data={
                    "payment_link": {
                        "id": "plink_123",
                        "url": "https://square.link/u/sub_123",
                    }
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    response = await wallet.create_subscription(
        "PLAN123",
        1,
        FiatSubscriptionPaymentOptions(
            wallet_id="wallet_1",
            memo="Weekly Plan",
            success_url="https://lnbits.example/success",
        ),
    )

    assert response.ok is True
    assert client.calls[0][0] == "/v2/catalog/object/PLAN123"
    assert client.calls[1][0] == "/v2/catalog/object/ITEM123"
    assert client.calls[2][0] == "/v2/online-checkout/payment-links"
    payload = client.calls[2][1]["json"]
    assert payload["quick_pay"]["price_money"] == {"amount": 1500, "currency": "USD"}
    assert payload["checkout_options"] == {
        "redirect_url": "https://lnbits.example/success",
        "subscription_plan_id": "PLAN_VARIATION_123",
    }


@pytest.mark.anyio
async def test_square_wallet_create_subscription_invoice(settings: Settings):
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"

    wallet = SquareWallet()

    response = await wallet.create_invoice(
        amount=15,
        payment_hash="hash123",
        currency="USD",
        memo="Square subscription payment",
        extra={
            "fiat_method": "subscription",
            "subscription": {
                "checking_id": "payment_PAYMENT123",
                "payment_request": "https://square.example/invoice",
            },
        },
    )

    assert response.ok is True
    assert response.checking_id == "payment_PAYMENT123"
    assert response.payment_request == "https://square.example/invoice"


@pytest.mark.anyio
async def test_square_wallet_cancel_subscription(settings: Settings):
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"

    wallet = SquareWallet()
    client = MockHTTPClient([MockHTTPResponse(json_data={"subscription": {}})])
    wallet.client = client  # type: ignore[assignment]

    response = await wallet.cancel_subscription("SUBSCRIPTION123", "wallet_1")

    assert response.ok is True
    assert client.calls[0][0] == "/v2/subscriptions/SUBSCRIPTION123/cancel"


@pytest.mark.anyio
async def test_square_wallet_cancel_subscription_by_request_id(
    settings: Settings, mocker: MockerFixture
):
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"

    wallet = SquareWallet()
    client = MockHTTPClient([MockHTTPResponse(json_data={"subscription": {}})])
    wallet.client = client  # type: ignore[assignment]
    payment = Payment(
        checking_id="fiat_square_payment_PAYMENT123",
        payment_hash="hash123",
        wallet_id="wallet_1",
        amount=1000,
        fee=0,
        bolt11="lnbc1square",
        fiat_provider="square",
        extra={"subscription_request_id": "REQUEST123"},
        external_id="SUBSCRIPTION123",
    )
    get_payments_mock = mocker.patch(
        "lnbits.core.crud.payments.get_payments",
        AsyncMock(side_effect=[[], [payment]]),
    )

    response = await wallet.cancel_subscription("REQUEST123", "wallet_1")

    assert response.ok is True
    assert client.calls[0][0] == "/v2/subscriptions/SUBSCRIPTION123/cancel"
    assert get_payments_mock.await_count == 2


@pytest.mark.anyio
async def test_square_wallet_get_invoice_status(settings: Settings):
    settings.square_api_endpoint = "https://connect.squareupsandbox.com"
    settings.square_access_token = "square-token"
    settings.square_location_id = "LOC123"
    settings.square_api_version = "2026-01-22"

    wallet = SquareWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "order": {
                        "id": "ORDER123",
                        "state": "COMPLETED",
                        "tenders": [{"payment_id": "PAYMENT123"}],
                    }
                }
            ),
            MockHTTPResponse(json_data={"payment": {"status": "COMPLETED"}}),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    status = await wallet.get_invoice_status("fiat_square_order_ORDER123")

    assert status.success is True
    assert client.calls[0][0] == "/v2/orders/ORDER123"
    assert client.calls[1][0] == "/v2/payments/PAYMENT123"


@pytest.mark.anyio
async def test_create_wallet_revolut_fiat_invoice_success(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.revolut_enabled = True
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_limits.service_min_amount_sats = 0
    settings.revolut_limits.service_max_amount_sats = 0
    settings.revolut_limits.service_faucet_wallet_id = None

    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="revolut"
    )
    fiat_mock_response = FiatInvoiceResponse(
        ok=True,
        checking_id="order_ORDER123",
        payment_request="https://checkout.revolut.com/payment-link/ORDER123",
    )

    mocker.patch(
        "lnbits.fiat.RevolutWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),
    )
    payment = await payments.create_fiat_invoice(to_wallet.id, invoice_data)
    assert payment.status == PaymentState.PENDING
    assert payment.fiat_provider == "revolut"
    assert payment.extra.get("fiat_checking_id") == fiat_mock_response.checking_id
    assert payment.checking_id.startswith("fiat_revolut_order_ORDER123")


@pytest.mark.anyio
async def test_revolut_wallet_create_invoice(settings: Settings):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"
    settings.revolut_payment_success_url = "https://lnbits.example/success"

    wallet = RevolutWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "id": "ORDER123",
                    "checkout_url": "https://checkout.revolut.com/payment-link/abc123",
                }
            )
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    response = await wallet.create_invoice(
        amount=1.23,
        payment_hash="hash123",
        currency="USD",
        memo="LNbits Revolut invoice",
        extra={"checkout": {"metadata": {"source": "test"}}},
    )

    assert response.ok is True
    assert response.checking_id == "order_ORDER123"
    assert (
        response.payment_request == "https://checkout.revolut.com/payment-link/abc123"
    )
    assert client.calls[0][0] == "/api/orders"
    payload = client.calls[0][1]["json"]
    assert payload["amount"] == 123
    assert payload["currency"] == "USD"
    assert payload["metadata"]["payment_hash"] == "hash123"
    assert payload["metadata"]["alan_action"] == "invoice"
    assert payload["metadata"]["source"] == "test"
    assert payload["redirect_url"] == "https://lnbits.example/success"


@pytest.mark.anyio
async def test_revolut_wallet_create_invoice_uses_currency_minor_units(
    settings: Settings,
):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "id": "ORDER_JPY",
                    "checkout_url": "https://checkout.revolut.com/payment-link/jpy",
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "ORDER_KWD",
                    "checkout_url": "https://checkout.revolut.com/payment-link/kwd",
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    await wallet.create_invoice(
        amount=123,
        payment_hash="hash_jpy",
        currency="JPY",
    )
    await wallet.create_invoice(
        amount=1.234,
        payment_hash="hash_kwd",
        currency="KWD",
    )

    assert client.calls[0][1]["json"]["amount"] == 123
    assert client.calls[1][1]["json"]["amount"] == 1234


@pytest.mark.anyio
async def test_revolut_wallet_get_invoice_status(settings: Settings):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    client = MockHTTPClient([MockHTTPResponse(json_data={"state": "COMPLETED"})])
    wallet.client = client  # type: ignore[assignment]

    status = await wallet.get_invoice_status("fiat_revolut_order_ORDER123")

    assert status.success is True
    assert client.calls[0][0] == "/api/orders/ORDER123"


@pytest.mark.anyio
async def test_revolut_wallet_create_subscription(settings: Settings):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"
    settings.revolut_payment_success_url = "https://lnbits.example/subscription-success"

    wallet = RevolutWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "customers": [
                        {
                            "id": "CUSTOMER123",
                            "email": "customer@example.com",
                        }
                    ]
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "SUBSCRIPTION123",
                    "setup_order_id": "ORDER123",
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "ORDER123",
                    "checkout_url": "https://checkout.revolut.com/payment-link/sub_123",
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    payment_options = FiatSubscriptionPaymentOptions(
        wallet_id="wallet_1",
        memo="Monthly Gold",
        tag="gold",
        customer_email="customer@example.com",
        extra={"link": "link-1"},
        success_url="https://lnbits.example/subscription-success",
    )

    response = await wallet.create_subscription(
        "PLAN_VARIATION_123", 1, payment_options
    )

    assert response.ok is True
    assert response.subscription_request_id is not None
    assert (
        response.checkout_session_url
        == "https://checkout.revolut.com/payment-link/sub_123"
    )
    assert client.calls[0][0] == "/api/customers"
    assert client.calls[0][1]["params"] == {"limit": 500}
    assert client.calls[0][1]["timeout"] == 30
    assert client.calls[1][0] == "/api/subscriptions"
    payload = client.calls[1][1]["json"]
    assert payload["plan_variation_id"] == "PLAN_VARIATION_123"
    assert payload["customer_id"] == "CUSTOMER123"
    assert client.calls[1][1]["timeout"] == 30
    assert client.calls[1][1]["headers"]["Idempotency-Key"] == (
        response.subscription_request_id
    )
    assert payload["setup_order_redirect_url"] == (
        "https://lnbits.example/subscription-success"
    )
    reference = json.loads(payload["external_reference"])
    assert reference["wallet_id"] == "wallet_1"
    assert reference["tag"] == "gold"
    assert reference["subscription_request_id"] == response.subscription_request_id
    assert reference["memo"] == "Monthly Gold"
    assert reference["extra"]["link"] == "link-1"
    assert client.calls[2][0] == "/api/orders/ORDER123"


@pytest.mark.anyio
async def test_revolut_wallet_create_subscription_uses_customer_email(
    settings: Settings,
):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "customers": [
                        {
                            "id": "CUSTOMER123",
                            "email": "customer@example.com",
                        }
                    ]
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "SUBSCRIPTION123",
                    "setup_order_id": "ORDER123",
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "ORDER123",
                    "checkout_url": "https://checkout.revolut.com/payment-link/sub_123",
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    payment_options = FiatSubscriptionPaymentOptions(
        wallet_id="wallet_1",
        customer_email="customer@example.com",
    )

    response = await wallet.create_subscription(
        "PLAN_VARIATION_123", 1, payment_options
    )

    assert response.ok is True
    assert client.calls[0][0] == "/api/customers"
    assert client.calls[0][1]["params"] == {"limit": 500}
    assert client.calls[0][1]["timeout"] == 30
    assert client.calls[1][0] == "/api/subscriptions"
    assert client.calls[1][1]["json"]["customer_id"] == "CUSTOMER123"
    assert client.calls[1][1]["timeout"] == 30
    assert client.calls[2][0] == "/api/orders/ORDER123"
    assert client.calls[2][1]["timeout"] == 30


@pytest.mark.anyio
async def test_revolut_wallet_create_subscription_uses_paginated_customer_email(
    settings: Settings,
):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "next_page_token": "PAGE2",
                    "customers": [
                        {
                            "id": "OTHER_CUSTOMER",
                            "email": "other@example.com",
                        }
                    ],
                }
            ),
            MockHTTPResponse(
                json_data={
                    "customers": [
                        {
                            "id": "CUSTOMER123",
                            "email": "customer@example.com",
                        }
                    ],
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "SUBSCRIPTION123",
                    "setup_order_id": "ORDER123",
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "ORDER123",
                    "checkout_url": "https://checkout.revolut.com/payment-link/sub_123",
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    payment_options = FiatSubscriptionPaymentOptions(
        wallet_id="wallet_1",
        customer_email="customer@example.com",
    )

    response = await wallet.create_subscription(
        "PLAN_VARIATION_123", 1, payment_options
    )

    assert response.ok is True
    assert client.calls[0][0] == "/api/customers"
    assert client.calls[0][1]["params"] == {"limit": 500}
    assert client.calls[1][0] == "/api/customers"
    assert client.calls[1][1]["params"] == {
        "limit": 500,
        "page_token": "PAGE2",
    }
    assert client.calls[1][1]["timeout"] == 30
    assert client.calls[2][0] == "/api/subscriptions"
    assert client.calls[2][1]["json"]["customer_id"] == "CUSTOMER123"
    assert client.calls[3][0] == "/api/orders/ORDER123"


@pytest.mark.anyio
async def test_revolut_wallet_create_subscription_creates_customer(settings: Settings):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                json_data={
                    "next_page_token": "PAGE2",
                    "customers": [
                        {
                            "id": "OTHER_CUSTOMER",
                            "email": "other@example.com",
                        }
                    ],
                }
            ),
            MockHTTPResponse(json_data={"customers": []}),
            MockHTTPResponse(json_data={"id": "CUSTOMER123"}),
            MockHTTPResponse(
                json_data={
                    "id": "SUBSCRIPTION123",
                    "setup_order_id": "ORDER123",
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "ORDER123",
                    "checkout_url": "https://checkout.revolut.com/payment-link/sub_123",
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    payment_options = FiatSubscriptionPaymentOptions(
        wallet_id="wallet_1",
        customer_email="customer@example.com",
    )

    response = await wallet.create_subscription(
        "PLAN_VARIATION_123", 1, payment_options
    )

    assert response.ok is True
    assert client.calls[0][0] == "/api/customers"
    assert client.calls[0][1]["params"] == {"limit": 500}
    assert client.calls[1][0] == "/api/customers"
    assert client.calls[1][1]["params"] == {
        "limit": 500,
        "page_token": "PAGE2",
    }
    assert client.calls[2][0] == "/api/customers"
    assert client.calls[2][1]["json"] == {"email": "customer@example.com"}
    assert client.calls[2][1]["timeout"] == 30
    assert client.calls[3][0] == "/api/subscriptions"
    assert client.calls[3][1]["json"]["customer_id"] == "CUSTOMER123"
    assert client.calls[4][0] == "/api/orders/ORDER123"


@pytest.mark.anyio
async def test_revolut_wallet_create_subscription_stops_customer_lookup_after_20_pages(
    settings: Settings,
):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    customer_pages = [
        MockHTTPResponse(
            json_data={
                "next_page_token": f"PAGE{page + 2}",
                "customers": [
                    {
                        "id": f"OTHER_CUSTOMER_{page}",
                        "email": f"other-{page}@example.com",
                    }
                ],
            }
        )
        for page in range(20)
    ]
    client = MockHTTPClient(
        [
            *customer_pages,
            MockHTTPResponse(json_data={"id": "CUSTOMER123"}),
            MockHTTPResponse(
                json_data={
                    "id": "SUBSCRIPTION123",
                    "setup_order_id": "ORDER123",
                }
            ),
            MockHTTPResponse(
                json_data={
                    "id": "ORDER123",
                    "checkout_url": "https://checkout.revolut.com/payment-link/sub_123",
                }
            ),
        ]
    )
    wallet.client = client  # type: ignore[assignment]

    payment_options = FiatSubscriptionPaymentOptions(
        wallet_id="wallet_1",
        customer_email="customer@example.com",
    )

    response = await wallet.create_subscription(
        "PLAN_VARIATION_123", 1, payment_options
    )

    assert response.ok is True
    assert [call[0] for call in client.calls[:20]] == ["/api/customers"] * 20
    assert client.calls[0][1]["params"] == {"limit": 500}
    assert client.calls[19][1]["params"] == {
        "limit": 500,
        "page_token": "PAGE20",
    }
    assert client.calls[20][0] == "/api/customers"
    assert client.calls[20][1]["json"] == {"email": "customer@example.com"}
    assert client.calls[21][0] == "/api/subscriptions"
    assert client.calls[21][1]["json"]["customer_id"] == "CUSTOMER123"
    assert client.calls[22][0] == "/api/orders/ORDER123"


@pytest.mark.anyio
async def test_revolut_wallet_create_subscription_requires_customer_email(
    settings: Settings,
):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    client = MockHTTPClient([])
    wallet.client = client  # type: ignore[assignment]

    payment_options = FiatSubscriptionPaymentOptions(wallet_id="wallet_1")

    response = await wallet.create_subscription(
        "PLAN_VARIATION_123", 1, payment_options
    )

    assert response.ok is False
    assert response.error_message == "Revolut subscriptions require customer_email."
    assert client.calls == []


@pytest.mark.anyio
async def test_revolut_wallet_cancel_subscription(settings: Settings):
    settings.revolut_api_endpoint = "https://sandbox-merchant.revolut.com"
    settings.revolut_api_secret_key = "revolut-secret"
    settings.revolut_api_version = "2026-04-20"

    wallet = RevolutWallet()
    client = MockHTTPClient([MockHTTPResponse(json_data={})])
    wallet.client = client  # type: ignore[assignment]

    response = await wallet.cancel_subscription("SUBSCRIPTION123", "wallet_1")

    assert response.ok is True
    assert client.calls[0][0] == "/api/subscriptions/SUBSCRIPTION123/cancel"


@pytest.mark.anyio
async def test_revolut_wallet_create_webhook(mocker: MockerFixture):
    client = MockHTTPClient(
        [
            MockHTTPResponse({"webhooks": []}),
            MockHTTPResponse(
                {
                    "id": "webhook_1",
                    "url": "https://lnbits.example/api/v1/callback/revolut",
                    "events": REVOLUT_WEBHOOK_EVENTS,
                    "signing_secret": "whsec_1",
                }
            ),
        ]
    )
    async_client = mocker.patch("lnbits.fiat.revolut.httpx.AsyncClient")
    async_client.return_value = client

    response = await RevolutWallet.create_webhook(
        url="https://lnbits.example/api/v1/callback/revolut",
        endpoint="https://sandbox-merchant.revolut.com",
        api_secret_key="revolut-secret",
        api_version="2026-04-20",
    )

    assert response["signing_secret"] == "whsec_1"
    async_client.assert_called_once()
    assert async_client.call_args.kwargs["base_url"] == (
        "https://sandbox-merchant.revolut.com"
    )
    assert async_client.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer revolut-secret"
    )
    assert client.calls == [
        (
            "/api/webhooks",
            {
                "timeout": 30,
            },
        ),
        (
            "/api/webhooks",
            {
                "json": {
                    "url": "https://lnbits.example/api/v1/callback/revolut",
                    "events": REVOLUT_WEBHOOK_EVENTS,
                },
                "timeout": 30,
            },
        ),
    ]


@pytest.mark.anyio
async def test_revolut_wallet_reuses_existing_webhook(mocker: MockerFixture):
    client = MockHTTPClient(
        [
            MockHTTPResponse(
                {
                    "webhooks": [
                        {
                            "id": "webhook_1",
                            "url": "https://lnbits.example/api/v1/callback/revolut",
                            "events": REVOLUT_WEBHOOK_EVENTS,
                            "signing_secret": "whsec_1",
                        }
                    ]
                }
            )
        ]
    )
    async_client = mocker.patch("lnbits.fiat.revolut.httpx.AsyncClient")
    async_client.return_value = client

    response = await RevolutWallet.create_webhook(
        url="https://lnbits.example/api/v1/callback/revolut",
        endpoint="https://sandbox-merchant.revolut.com",
        api_secret_key="revolut-secret",
        api_version="2026-04-20",
    )

    assert response["already_exists"] is True
    assert response["signing_secret"] == "whsec_1"
    assert client.calls == [
        (
            "/api/webhooks",
            {
                "timeout": 30,
            },
        )
    ]


@pytest.mark.anyio
async def test_revolut_wallet_rejects_local_webhook_url():
    with pytest.raises(ValueError, match="clearnet URL"):
        await RevolutWallet.create_webhook(
            url="http://localhost:5000/api/v1/callback/revolut",
            endpoint="https://sandbox-merchant.revolut.com",
            api_secret_key="revolut-secret",
            api_version="2026-04-20",
        )


def test_check_revolut_signature():
    payload = b'{"event":"ORDER_COMPLETED","order_id":"ORDER123"}'
    timestamp = str(int(time.time() * 1000))
    secret = "revolut-secret"
    signed_payload = b"v1." + timestamp.encode() + b"." + payload
    sig = "v1=" + hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    check_revolut_signature(payload, sig, timestamp, secret)


def test_check_revolut_signature_rejects_payload_only_signature():
    payload = b'{"event":"ORDER_COMPLETED","order_id":"ORDER123"}'
    timestamp = str(int(time.time() * 1000))
    secret = "revolut-secret"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with pytest.raises(ValueError, match="signature verification failed"):
        check_revolut_signature(payload, sig, timestamp, secret)


def test_check_revolut_signature_v1_header():
    payload = b'{"event":"ORDER_COMPLETED","order_id":"ORDER123"}'
    timestamp = str(int(time.time() * 1000))
    secret = "revolut-secret"
    signed_payload = b"v1." + timestamp.encode() + b"." + payload
    sig = "v1=" + hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    check_revolut_signature(payload, sig, timestamp, secret)


def test_check_revolut_signature_multiple_v1_headers():
    payload = b'{"event":"ORDER_COMPLETED","order_id":"ORDER123"}'
    timestamp = str(int(time.time() * 1000))
    secret = "revolut-secret"
    signed_payload = b"v1." + timestamp.encode() + b"." + payload
    valid_sig = (
        "v1=" + hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    )
    sig_header = f"v1=deadbeef,{valid_sig}"

    check_revolut_signature(payload, sig_header, timestamp, secret)


def test_check_revolut_signature_docs_vector():
    payload = (
        b'{"data":{"id":"645a7696-22f3-aa47-9c74-cbae0449cc46",'
        b'"new_state":"completed","old_state":"pending",'
        b'"request_id":"app_charges-9f5d5eb3-1e06-46c5-b1c0-3914763e0bcb"},'
        b'"event":"TransactionStateChanged",'
        b'"timestamp":"2023-05-09T16:36:38.028960Z"}'
    )
    timestamp = "1683650202360"
    secret = "wsk_r59a4HfWVAKycbCaNO1RvgCJec02gRd8"
    sig = "v1=bca326fb378d0da7f7c490ad584a8106bab9723d8d9cdd0d50b4c5b3be3837c0"

    check_revolut_signature(
        payload, sig, timestamp, secret, tolerance_seconds=100000000
    )


@pytest.mark.anyio
async def test_fiat_service_fee(settings: Settings):
    # settings.stripe_limits.service_min_amount_sats = 0
    amount_msats = 100_000
    fee = payments.service_fee_fiat(amount_msats, "no_such_fiat_provider")
    assert fee == 0

    settings.stripe_limits.service_fee_wallet_id = None
    fee = payments.service_fee_fiat(amount_msats, "stripe")
    assert fee == 0

    settings.stripe_limits.service_fee_wallet_id = "wallet_id"
    fee = payments.service_fee_fiat(amount_msats, "stripe")
    assert fee == 0

    settings.stripe_limits.service_max_fee_sats = 5
    settings.stripe_limits.service_fee_percent = 20
    fee = payments.service_fee_fiat(amount_msats, "stripe")
    assert fee == 5000

    fee = payments.service_fee_fiat(-amount_msats, "stripe")
    assert fee == 5000

    settings.stripe_limits.service_max_fee_sats = 5
    settings.stripe_limits.service_fee_percent = 3
    fee = payments.service_fee_fiat(amount_msats, "stripe")
    assert fee == 3000

    fee = payments.service_fee_fiat(-amount_msats, "stripe")
    assert fee == 3000


@pytest.mark.anyio
async def test_handle_fiat_payment_confirmation(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    user = await create_user_account()
    service_fee_wallet = await create_wallet(user_id=user.id)
    faucet_wallet = await create_wallet(user_id=user.id)
    await payments.update_wallet_balance(wallet=faucet_wallet, amount=100_000_000)

    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="stripe"
    )

    settings.stripe_enabled = True
    settings.stripe_limits.service_min_amount_sats = 0
    settings.stripe_limits.service_max_amount_sats = 0

    settings.stripe_limits.service_fee_percent = 20
    settings.stripe_limits.service_fee_wallet_id = service_fee_wallet.id
    settings.stripe_limits.service_faucet_wallet_id = faucet_wallet.id

    fiat_mock_response = FiatInvoiceResponse(
        ok=True,
        checking_id=f"session_1000_{get_random_string(10)}",
        payment_request="https://stripe.com/pay/session_1000",
    )

    mocker.patch(
        "lnbits.fiat.StripeWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=10000),  # 1 BTC = 100 000 USD, so 1 USD = 1000 sats
    )
    payment = await payments.create_fiat_invoice(to_wallet.id, invoice_data)
    assert payment.status == PaymentState.PENDING
    assert payment.amount == 10_000_000

    await handle_fiat_payment_confirmation(payment)
    # await asyncio.sleep(1)  # Simulate async delay

    service_fee_payments = await get_payments(wallet_id=service_fee_wallet.id)
    assert len(service_fee_payments) == 1
    assert service_fee_payments[0].amount == 2_000_000
    assert service_fee_payments[0].fee == 0
    assert service_fee_payments[0].status == PaymentState.SUCCESS
    assert service_fee_payments[0].fiat_provider is None

    faucet_wallet_payments = await get_payments(wallet_id=faucet_wallet.id)

    # Background tasks may create more payments, so we check for at least 2
    # One for the service fee, one for the top-up)
    assert len(faucet_wallet_payments) >= 2
    faucet_payment = next(
        (p for p in faucet_wallet_payments if p.payment_hash == payment.payment_hash),
        None,
    )
    assert faucet_payment
    assert faucet_payment.amount == -10_000_000
    assert faucet_payment.fee == 0
    assert faucet_payment.status == PaymentState.SUCCESS
    assert faucet_payment.fiat_provider is None
    assert (
        faucet_payment.extra.get("fiat_checking_id") == fiat_mock_response.checking_id
    )
    assert (
        faucet_payment.extra.get("fiat_payment_request")
        == fiat_mock_response.payment_request
    )
    assert faucet_payment.checking_id.startswith("internal_fiat_stripe_")


@pytest.mark.parametrize("payload", [b'{"id": "evt_test"}', b"{}", b""])
def test_check_stripe_signature_success(payload):
    secret = "whsec_testsecret"
    sig_header, _, _ = _make_stripe_sig_header(payload, secret)
    # Should not raise
    check_stripe_signature(payload, sig_header, secret)


@pytest.mark.parametrize("payload", [b'{"id": "evt_test"}'])
def test_check_stripe_signature_missing_header(payload):
    secret = "whsec_testsecret"
    with pytest.raises(ValueError, match="Stripe-Signature header is missing"):
        check_stripe_signature(payload, None, secret)


def test_check_stripe_signature_missing_secret():
    payload = b'{"id": "evt_test"}'
    sig_header, _, _ = _make_stripe_sig_header(payload, "whsec_testsecret")
    with pytest.raises(ValueError, match="Stripe webhook cannot be verified"):
        check_stripe_signature(payload, sig_header, None)


def test_check_stripe_signature_invalid_signature():
    payload = b'{"id": "evt_test"}'
    secret = "whsec_testsecret"
    _, timestamp, _ = _make_stripe_sig_header(payload, secret)
    # Tamper with signature
    bad_sig_header = f"t={timestamp},v1=deadbeef"
    with pytest.raises(ValueError, match="Stripe signature verification failed"):
        check_stripe_signature(payload, bad_sig_header, secret)


def test_check_stripe_signature_old_timestamp():
    payload = b'{"id": "evt_test"}'
    secret = "whsec_testsecret"
    old_timestamp = int(time.time()) - 10000  # way outside default tolerance
    sig_header, _, _ = _make_stripe_sig_header(payload, secret, timestamp=old_timestamp)
    with pytest.raises(ValueError, match="Timestamp outside tolerance"):
        check_stripe_signature(payload, sig_header, secret)


def test_check_stripe_signature_future_timestamp():
    payload = b'{"id": "evt_test"}'
    secret = "whsec_testsecret"
    future_timestamp = int(time.time()) + 10000
    sig_header, _, _ = _make_stripe_sig_header(
        payload, secret, timestamp=future_timestamp
    )
    with pytest.raises(ValueError, match="Timestamp outside tolerance"):
        check_stripe_signature(payload, sig_header, secret)


def test_check_stripe_signature_malformed_header():
    payload = b'{"id": "evt_test"}'
    secret = "whsec_testsecret"
    # Missing v1 part
    bad_header = "t=1234567890"
    with pytest.raises(Exception):  # noqa: B017
        check_stripe_signature(payload, bad_header, secret)
    # Missing t part
    bad_header2 = "v1=abcdef"
    with pytest.raises(Exception):  # noqa: B017
        check_stripe_signature(payload, bad_header2, secret)
    # Not split by =
    bad_header3 = "t1234567890,v1abcdef"
    with pytest.raises(Exception):  # noqa: B017
        check_stripe_signature(payload, bad_header3, secret)


def test_check_stripe_signature_non_utf8_payload():
    secret = "whsec_testsecret"
    payload = b"\xff\xfe\xfd"  # not valid utf-8
    timestamp = int(time.time())
    # This will raise UnicodeDecodeError inside check_stripe_signature
    signed_payload = f"{timestamp}." + payload.decode(errors="ignore")
    signature = hmac.new(
        secret.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()
    sig_header = f"t={timestamp},v1={signature}"
    with pytest.raises(UnicodeDecodeError):
        check_stripe_signature(payload, sig_header, secret)


def test_check_square_signature_success():
    payload = b'{"type":"payment.updated"}'
    secret = "signature-key"
    notification_url = "https://lnbits.example/api/v1/callback/square"
    signature = b64encode(
        hmac.new(
            key=secret.encode(),
            msg=notification_url.encode() + payload,
            digestmod=hashlib.sha256,
        ).digest()
    ).decode()

    check_square_signature(payload, signature, secret, notification_url)


def test_check_square_signature_rejects_invalid_signature():
    with pytest.raises(ValueError, match="Square signature verification failed."):
        check_square_signature(
            b'{"type":"payment.updated"}',
            "invalid-signature",
            "signature-key",
            "https://lnbits.example/api/v1/callback/square",
        )


# Helper to generate a valid Stripe signature header
def _make_stripe_sig_header(payload, secret, timestamp=None):
    if timestamp is None:
        timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(
        secret.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}", timestamp, signature


@pytest.mark.anyio
async def test_check_fiat_status_handles_internal_states(mocker: MockerFixture):
    pending_payment = Payment(
        checking_id="external_payment",
        payment_hash="hash_pending",
        wallet_id="wallet_id",
        amount=1000,
        fee=0,
        bolt11="bolt11",
        status=PaymentState.PENDING,
    )
    success_payment = Payment(
        checking_id="fiat_success",
        payment_hash="hash_success",
        wallet_id="wallet_id",
        amount=1000,
        fee=0,
        bolt11="bolt11",
        status=PaymentState.SUCCESS,
        fiat_provider="stripe",
    )
    failed_payment = Payment(
        checking_id="fiat_failed",
        payment_hash="hash_failed",
        wallet_id="wallet_id",
        amount=1000,
        fee=0,
        bolt11="bolt11",
        status=PaymentState.FAILED,
        fiat_provider="stripe",
    )

    assert (await check_fiat_status(pending_payment)).pending is True
    assert (await check_fiat_status(success_payment)).success is True
    assert (await check_fiat_status(failed_payment)).failed is True

    provider = mocker.Mock()
    provider.get_invoice_status = AsyncMock(return_value=FiatPaymentStatus(paid=True))
    mocker.patch(
        "lnbits.core.services.fiat_providers.get_fiat_provider",
        AsyncMock(return_value=provider),
    )
    queue_put = mocker.patch("lnbits.tasks.internal_invoice_queue.put", AsyncMock())

    success_status = await check_fiat_status(
        Payment(
            checking_id="fiat_pending",
            payment_hash="hash_queue",
            wallet_id="wallet_id",
            amount=1000,
            fee=0,
            bolt11="bolt11",
            status=PaymentState.PENDING,
            fiat_provider="stripe",
            extra={"fiat_checking_id": "stripe_checking_id"},
        )
    )

    assert success_status.success is True
    queue_put.assert_awaited_once_with("fiat_pending")

    await check_fiat_status(
        Payment(
            checking_id="fiat_pending_skip",
            payment_hash="hash_skip",
            wallet_id="wallet_id",
            amount=1000,
            fee=0,
            bolt11="bolt11",
            status=PaymentState.PENDING,
            fiat_provider="stripe",
            extra={"fiat_checking_id": "stripe_checking_id"},
        ),
        skip_internal_payment_notifications=True,
    )
    assert queue_put.await_count == 1


@pytest.mark.anyio
async def test_verify_paypal_webhook_requires_configuration(settings: Settings):
    settings.paypal_webhook_id = None

    with pytest.raises(
        ValueError, match="PayPal webhook cannot be verified. Missing webhook ID."
    ):
        await verify_paypal_webhook({}, b"{}")


@pytest.mark.anyio
async def test_verify_paypal_webhook_requires_headers(settings: Settings):
    settings.paypal_webhook_id = "webhook-id"

    with pytest.raises(
        ValueError, match="PayPal webhook cannot be verified. Missing headers."
    ):
        await verify_paypal_webhook({}, b"{}")


@pytest.mark.anyio
async def test_verify_paypal_webhook_success(settings: Settings, mocker: MockerFixture):
    settings.paypal_webhook_id = "webhook-id"
    client = MockHTTPClient(
        [
            MockHTTPResponse(json_data={"access_token": "token"}),
            MockHTTPResponse(json_data={"verification_status": "SUCCESS"}),
        ]
    )
    mocker.patch(
        "lnbits.core.services.fiat_providers.httpx.AsyncClient",
        return_value=client,
    )

    await verify_paypal_webhook(
        {
            "PAYPAL-TRANSMISSION-ID": "tx-id",
            "PAYPAL-TRANSMISSION-TIME": "2024-01-01T00:00:00Z",
            "PAYPAL-TRANSMISSION-SIG": "signature",
            "PAYPAL-CERT-URL": "https://cert.example.com",
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        },
        b'{"id":"event-1"}',
    )

    assert client.calls[0][0] == "/v1/oauth2/token"
    assert client.calls[1][0] == "/v1/notifications/verify-webhook-signature"
    assert client.calls[1][1]["headers"]["Authorization"] == "Bearer token"


@pytest.mark.anyio
async def test_verify_paypal_webhook_raises_on_failed_verification(
    settings: Settings, mocker: MockerFixture
):
    settings.paypal_webhook_id = "webhook-id"
    client = MockHTTPClient(
        [
            MockHTTPResponse(json_data={"access_token": "token"}),
            MockHTTPResponse(json_data={"verification_status": "FAILURE"}),
        ]
    )
    mocker.patch(
        "lnbits.core.services.fiat_providers.httpx.AsyncClient",
        return_value=client,
    )

    with pytest.raises(ValueError, match="PayPal webhook cannot be verified."):
        await verify_paypal_webhook(
            {
                "PAYPAL-TRANSMISSION-ID": "tx-id",
                "PAYPAL-TRANSMISSION-TIME": "2024-01-01T00:00:00Z",
                "PAYPAL-TRANSMISSION-SIG": "signature",
                "PAYPAL-CERT-URL": "https://cert.example.com",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            },
            b'{"id":"event-1"}',
        )


@pytest.mark.anyio
async def test_test_connection_reports_provider_status(mocker: MockerFixture):
    mocker.patch(
        "lnbits.core.services.fiat_providers.get_fiat_provider",
        AsyncMock(return_value=None),
    )
    missing_status = await fiat_provider_connection("stripe")
    assert missing_status.success is False
    assert missing_status.message == "Fiat provider 'stripe' not found."

    provider = mocker.Mock()
    provider.status = AsyncMock(
        return_value=FiatStatusResponse(error_message="bad key")
    )
    mocker.patch(
        "lnbits.core.services.fiat_providers.get_fiat_provider",
        AsyncMock(return_value=provider),
    )
    error_status = await fiat_provider_connection("stripe")
    assert error_status.success is False
    assert error_status.message == "Cconnection test failed: bad key"

    provider.status = AsyncMock(return_value=FiatStatusResponse(balance=21.0))
    success_status = await fiat_provider_connection("stripe")
    assert success_status.success is True
    assert success_status.message == "Connection test successful. Balance: 21.0."
