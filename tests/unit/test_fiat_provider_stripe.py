from unittest.mock import AsyncMock

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.payments import CreateInvoice
from lnbits.core.models.wallets import Wallet
from lnbits.core.services import payments
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
async def test_create_wallet_fiat_invoice_success(
    to_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.stripe_enabled = True
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    invoice_data = CreateInvoice(
        unit="USD", amount=1.0, memo="Test", fiat_provider="stripe"
    )

    settings.stripe_enabled = True
    fiat_mock_response = FiatInvoiceResponse(
        ok=True,
        checking_id="session_123",
        payment_request="https://stripe.com/pay/session_123",
    )

    mocker.patch(
        "lnbits.walletsfiat.StripeWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
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


# @pytest.mark.anyio
# async def test_create_wallet_fiat_invoice_fiat_limits_fail(
#     to_wallet: Wallet,
#     settings: Settings,
# ):
#     settings.stripe_enabled = True

#     invoice_data = CreateInvoice(
#         unit="USD", amount=1.0, memo="Test", fiat_provider="stripe"
#     )

#     with pytest.raises(
#         ValueError, match="Fiat provider 'notarealprovider' is not enabled"
#     ):
#         await payments.create_wallet_fiat_invoice("wallet_id", invoice_data)
