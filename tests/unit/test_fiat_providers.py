import hashlib
import hmac
import time
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
    check_stripe_signature,
    handle_fiat_payment_confirmation,
    test_connection as fiat_provider_connection,
    verify_paypal_webhook,
)
from lnbits.core.services.users import create_user_account
from lnbits.fiat.base import FiatInvoiceResponse, FiatPaymentStatus, FiatStatusResponse
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


@pytest.fixture(autouse=True)
def fiat_provider_test_settings(settings: Settings):
    original_allowed_currencies = settings.lnbits_allowed_currencies
    original_paypal_enabled = settings.paypal_enabled
    settings.lnbits_allowed_currencies = []
    settings.paypal_enabled = False
    yield
    settings.lnbits_allowed_currencies = original_allowed_currencies
    settings.paypal_enabled = original_paypal_enabled


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
async def test_verify_paypal_webhook_success(
    settings: Settings, mocker: MockerFixture
):
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
    provider.status = AsyncMock(return_value=FiatStatusResponse(error_message="bad key"))
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
