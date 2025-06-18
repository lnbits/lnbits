from unittest.mock import AsyncMock

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud.wallets import create_wallet
from lnbits.core.models.payments import CreateInvoice
from lnbits.core.models.wallets import Wallet
from lnbits.core.services import payments
from lnbits.core.services.users import create_user_account
from lnbits.settings import Settings
from lnbits.walletsfiat.base import FiatInvoiceResponse


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_missing_provider():
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider=None
    )
    with pytest.raises(ValueError, match="Fiat provider is required"):
        await payments.create_wallet_fiat_invoice("wallet_id", invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_provider_not_enabled(settings: Settings):
    settings.stripe_enabled = False
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="notarealprovider"
    )
    with pytest.raises(
        ValueError, match="Fiat provider 'notarealprovider' is not enabled"
    ):
        await payments.create_wallet_fiat_invoice("wallet_id", invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_with_sat_unit(settings: Settings):
    settings.stripe_enabled = True
    invoice_data = CreateInvoice(
        unit="sat", amount=1.0, memo="Test", fiat_provider="stripe"
    )
    with pytest.raises(ValueError, match="Fiat provider cannot be used with satoshis"):
        await payments.create_wallet_fiat_invoice("wallet_id", invoice_data)


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
        await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_min_amount_sats = 1001
    settings.stripe_limits.service_max_amount_sats = 10000

    with pytest.raises(ValueError, match="Minimum amount is 1001 sats for 'stripe'."):
        await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_min_amount_sats = 10
    settings.stripe_limits.service_max_amount_sats = 10000
    settings.stripe_limits.service_max_fee_sats = 100

    with pytest.raises(
        ValueError, match="Fiat provider 'stripe' service fee wallet missing."
    ):
        await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_fee_wallet_id = "not_a_real_wallet_id"

    with pytest.raises(
        ValueError, match="Fiat provider 'stripe' service fee wallet not found."
    ):
        await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)

    settings.stripe_limits.service_fee_wallet_id = to_wallet.id
    settings.stripe_limits.service_faucet_wallet_id = "not_a_real_wallet_id"

    with pytest.raises(
        ValueError, match="Fiat provider 'stripe' faucet wallet not found."
    ):
        await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    settings.stripe_limits.service_faucet_wallet_id = wallet.id

    with pytest.raises(
        ValueError, match="The amount exceeds the 'stripe'faucet wallet balance."
    ):
        await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_provider_fails(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.stripe_enabled = True
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="stripe"
    )

    fiat_mock_response = FiatInvoiceResponse(
        ok=False,
        error_message="Failed to create invoice",
    )

    mocker.patch(
        "lnbits.walletsfiat.StripeWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),  # 1 BTC = 100 000 USD, so 1 USD = 1000 sats
    )

    with pytest.raises(ValueError, match="Cannot create payment request for 'stripe'."):
        await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)


@pytest.mark.anyio
async def test_create_wallet_fiat_invoice_success(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="stripe"
    )

    settings.stripe_enabled = True
    settings.stripe_limits.service_min_amount_sats = 0
    settings.stripe_limits.service_max_amount_sats = 0
    settings.stripe_limits.service_faucet_wallet_id = None
    fiat_mock_response = FiatInvoiceResponse(
        ok=True,
        checking_id="session_123",
        payment_request="https://stripe.com/pay/session_123",
    )

    mocker.patch(
        "lnbits.walletsfiat.StripeWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),  # 1 BTC = 100 000 USD, so 1 USD = 1000 sats
    )
    payment = await payments.create_wallet_fiat_invoice(to_wallet.id, invoice_data)
    assert payment.fiat_provider == "stripe"
    assert payment.extra.get("fiat_checking_id") == "session_123"
    assert (
        payment.extra.get("fiat_payment_request")
        == "https://stripe.com/pay/session_123"
    )
    assert payment.checking_id.startswith("internal_fiat_stripe_")
    assert payment.fee <= 0


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
