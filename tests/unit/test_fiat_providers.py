import hashlib
import hmac
import time
from unittest.mock import AsyncMock

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud.payments import get_payments
from lnbits.core.crud.users import get_user
from lnbits.core.crud.wallets import create_wallet
from lnbits.core.models.payments import CreateInvoice, PaymentState
from lnbits.core.models.users import User
from lnbits.core.models.wallets import Wallet
from lnbits.core.services import payments
from lnbits.core.services.fiat_providers import (
    check_stripe_signature,
    handle_fiat_payment_confirmation,
)
from lnbits.core.services.users import create_user_account
from lnbits.fiat.base import FiatInvoiceResponse, FiatPaymentStatus
from lnbits.settings import Settings
from tests.helpers import get_random_string


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

    status = await payment.check_status()
    assert status.success is False
    assert status.pending is True

    fiat_mock_status = FiatPaymentStatus(paid=True, fee=123)
    mocker.patch(
        "lnbits.fiat.StripeWallet.get_invoice_status",
        AsyncMock(return_value=fiat_mock_status),
    )
    status = await payment.check_status()
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
