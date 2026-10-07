from types import SimpleNamespace
from uuid import uuid4

import pytest

from lnbits.core.crud.payments import (
    create_payment,
    get_payments,
    get_wallet_payment_total_breakdown,
)
from lnbits.core.crud.users import create_account, get_accounts, get_user
from lnbits.core.crud.wallets import (
    create_wallet,
    delete_wallet,
    get_total_balance,
    get_wallet,
)
from lnbits.core.models import CreatePayment, Payment, PaymentState
from lnbits.core.models.payments import CreateInvoice
from lnbits.core.models.users import Account, AccountFilters
from lnbits.core.models.wallets import WalletType
from lnbits.core.services.fiat_providers import check_fiat_status
from lnbits.core.services.payments import (
    create_payment_request,
    create_wallet_invoice,
    pay_invoice,
)
from lnbits.db import Filter, Filters
from lnbits.exceptions import InvoiceError, PaymentError
from lnbits.fiat.base import FiatInvoiceResponse, FiatPaymentStatus
from lnbits.settings import Settings
from lnbits.wallets.fake import FakeWallet

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("provider", ["stripe", "paypal", "square", "revolut"])
@pytest.mark.parametrize(
    "flag,enabled,allowed,available",
    [
        (False, False, True, False),
        (False, True, False, False),
        (False, True, True, True),
        (True, False, False, True),
        (True, True, False, True),
    ],
)
async def test_fiat_wallet_creation_availability(
    client, from_wallet, settings, provider, flag, enabled, allowed, available
):
    settings.lnbits_allow_fiat_wallets = flag
    for name in ("stripe", "paypal", "square", "revolut"):
        setattr(settings, f"{name}_enabled", False)
    setattr(settings, f"{provider}_enabled", enabled)
    settings.get_fiat_provider_limits(provider).allowed_users = [
        from_wallet.user if allowed else uuid4().hex
    ]

    user = await get_user(from_wallet.user)
    assert user
    assert user.can_create_fiat_wallet is available
    assert (provider in user.fiat_providers) is (enabled and allowed)

    response = await client.post(
        f"/api/v1/wallet?usr={from_wallet.user}",
        json={"name": "Receipts", "wallet_type": "fiat"},
    )
    assert response.status_code == (200 if available else 403)
    if available:
        wallet = await get_wallet(response.json()["id"])
        assert wallet
        assert wallet.wallet_type == "fiat"
        assert wallet.can_receive_payments and wallet.can_view_payments
        assert not wallet.can_send_payments
        assert wallet.lightning_address is None

    lightning = await client.post(
        f"/api/v1/wallet?usr={from_wallet.user}", json={"name": "Lightning"}
    )
    assert lightning.status_code == 200
    assert lightning.json()["wallet_type"] == "lightning"


@pytest.mark.parametrize("method", ["cash", "stripe"])
async def test_fiat_wallet_receives_but_cannot_spend(
    client, from_wallet, settings, mocker, method
):
    wallet = await create_wallet(user_id=from_wallet.user, wallet_type=WalletType.FIAT)
    initial_total = await get_total_balance()
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        mocker.AsyncMock(return_value=1000),
    )
    data = CreateInvoice(
        amount=5,
        unit="USD",
        memo="Receipt",
        internal=True,
        extra={"fiat_method": method},
    )
    if method == "stripe":
        settings.stripe_enabled = True
        settings.stripe_limits.service_min_amount_sats = 0
        settings.stripe_limits.service_max_amount_sats = 0
        settings.stripe_limits.service_fee_percent = 0
        settings.stripe_limits.service_max_fee_sats = 0
        provider = mocker.Mock()
        provider.create_invoice = mocker.AsyncMock(
            return_value=FiatInvoiceResponse(ok=True, checking_id=uuid4().hex)
        )
        provider.get_invoice_status = mocker.AsyncMock(
            return_value=FiatPaymentStatus(paid=True)
        )
        for module in ("payments", "fiat_providers"):
            mocker.patch(
                f"lnbits.core.services.{module}.get_fiat_provider",
                mocker.AsyncMock(return_value=provider),
            )
        data.fiat_provider = "stripe"
        receipt = await create_payment_request(wallet.id, data)
        assert (await check_fiat_status(receipt)).success
    else:
        response = await client.post(
            "/api/v1/fiat/cash",
            headers={"X-Api-Key": wallet.adminkey},
            json={"amount": 5, "unit": "USD", "memo": "Receipt"},
        )
        assert response.status_code == 201
        receipt = Payment.parse_obj(response.json())
        assert receipt.success
    assert receipt.is_internal
    wallet = await get_wallet(wallet.id)
    assert wallet
    assert wallet.balance_msat > 0
    assert wallet.withdrawable_balance == 0
    assert len(await get_payments(wallet_id=wallet.id)) == 1
    assert await get_total_balance() == initial_total
    breakdown = await get_wallet_payment_total_breakdown(wallet.id)
    assert len(breakdown) == 1 and breakdown[0].is_fiat

    # Disabling creation must not turn an existing fiat wallet into a spendable one.
    settings.lnbits_allow_fiat_wallets = False
    settings.stripe_enabled = False
    invoice = await create_wallet_invoice(
        from_wallet.id, CreateInvoice(amount=1, memo="Cannot spend fiat balance")
    )
    dispatch = mocker.patch(
        "lnbits.core.services.payments._pay_invoice",
        mocker.AsyncMock(side_effect=AssertionError("Must not attempt payment")),
    )
    external = await FakeWallet().create_invoice(1, "External invoice")
    for bolt11 in (invoice.bolt11, external.payment_request):
        response = await client.post(
            "/api/v1/payments",
            headers={"X-Api-Key": wallet.adminkey},
            json={"out": True, "bolt11": bolt11},
        )
        assert response.status_code == 520
        assert "permission" in response.text

    mocker.patch(
        "lnbits.core.views.lnurl_api.fetch_lnurl_pay_request",
        mocker.AsyncMock(
            return_value=(
                SimpleNamespace(metadata=SimpleNamespace(text="LNURL payment")),
                SimpleNamespace(pr=invoice.bolt11, disposable=True, successAction=None),
            )
        ),
    )
    response = await client.post(
        "/api/v1/payments/lnurl",
        headers={"X-Api-Key": wallet.adminkey},
        json={"lnurl": "receiver@example.com", "amount": 1000},
    )
    assert response.status_code == 520
    assert "permission" in response.text

    # The service used by extensions, including withdrawals, enforces the same rule.
    with pytest.raises(PaymentError, match="permission to pay"):
        await pay_invoice(wallet_id=wallet.id, payment_request=invoice.bolt11)
    dispatch.assert_not_awaited()

    # The wallet API must not allow conversion into a spendable wallet.
    response = await client.patch(
        "/api/v1/wallet",
        headers={"X-Api-Key": wallet.adminkey},
        json={"wallet_type": "lightning"},
    )
    assert response.status_code == 200
    assert response.json()["wallet_type"] == "fiat"

    # Extensions must not bypass the restriction with a direct outgoing entry.
    with pytest.raises(ValueError, match="permission to spend"):
        await create_payment(
            checking_id=uuid4().hex,
            data=CreatePayment(
                wallet_id=wallet.id,
                payment_hash=uuid4().hex,
                bolt11="",
                amount_msat=-1000,
                memo="Blocked debit",
            ),
        )
    current = await get_wallet(wallet.id)
    assert current and current.balance_msat == wallet.balance_msat

    shared = await client.post(
        f"/api/v1/wallet?usr={from_wallet.user}",
        json={"wallet_type": "lightning-shared", "shared_wallet_id": wallet.id},
    )
    assert shared.status_code == 400


async def test_cash_validation_creates_and_settles_with_owner_admin_key(
    client, from_wallet, mocker
):
    wallet = await create_wallet(user_id=from_wallet.user, wallet_type=WalletType.FIAT)
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        mocker.AsyncMock(return_value=1000),
    )
    backend = mocker.patch("lnbits.core.services.payments.get_funding_source")
    notify = mocker.patch(
        "lnbits.core.views.fiat_api.task_manager.internal_invoice_queue.put_nowait"
    )
    data = {"amount": 12.34, "unit": "GBP", "internal_memo": "Till receipt"}
    for key in (None, wallet.inkey, from_wallet.adminkey):
        response = await client.post(
            "/api/v1/fiat/cash", headers={"X-Api-Key": key} if key else {}, json=data
        )
        assert response.status_code in (400, 401, 403)
    assert not await get_payments(wallet_id=wallet.id)
    notify.assert_not_called()

    response = await client.post(
        "/api/v1/fiat/cash", headers={"X-Api-Key": wallet.adminkey}, json=data
    )
    assert response.status_code == 201
    receipt = Payment.parse_obj(response.json())
    assert receipt.success and receipt.is_internal and receipt.fee == 0
    assert receipt.extra["fiat_method"] == "cash"
    assert receipt.extra["fiat_amount"] == 12.34
    assert receipt.extra["fiat_currency"] == "GBP"
    assert receipt.extra["internal_memo"] == "Till receipt"
    backend.assert_not_called()
    notify.assert_called_once()
    assert notify.call_args.args[0].success
    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 1 and payments[0].success
    current = await get_wallet(wallet.id)
    assert current and current.balance_msat == receipt.amount
    assert current.withdrawable_balance == 0


@pytest.mark.parametrize(
    "invalid",
    [
        {"amount": 0},
        {"amount": -1},
        {"unit": "sat"},
        {"unit": "INVALID"},
        {"fiat_provider": "stripe"},
        {"wallet_id": "another-wallet"},
        {"payment_hash": "00" * 32},
    ],
)
async def test_cash_validation_rejects_invalid_requests(client, from_wallet, invalid):
    wallet = await create_wallet(user_id=from_wallet.user, wallet_type=WalletType.FIAT)
    response = await client.post(
        "/api/v1/fiat/cash",
        headers={"X-Api-Key": wallet.adminkey},
        json={"amount": 5, "unit": "USD", **invalid},
    )
    assert response.status_code in (400, 422)
    assert not await get_payments(wallet_id=wallet.id)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"extra": {"fiat_method": "cash"}, "unit": "sat"},
        {"extra": {"fiat_method": "cash"}, "payment_hash": "00" * 32},
    ],
)
async def test_fiat_wallet_rejects_lightning_receiving(client, from_wallet, options):
    wallet = await create_wallet(user_id=from_wallet.user, wallet_type=WalletType.FIAT)
    response = await client.post(
        "/api/v1/payments",
        headers={"X-Api-Key": wallet.inkey},
        json={"out": False, "amount": 5, "unit": "USD", **options},
    )
    assert response.status_code == 520
    assert not await get_payments(wallet_id=wallet.id)


async def test_fiat_wallet_rejects_direct_lightning_invoice(from_wallet, mocker):
    wallet = await create_wallet(user_id=from_wallet.user, wallet_type=WalletType.FIAT)
    backend = mocker.patch("lnbits.core.services.payments.get_funding_source")
    with pytest.raises(InvoiceError, match="only accept cash or fiat provider"):
        await create_wallet_invoice(wallet.id, CreateInvoice(amount=5, memo="Blocked"))
    backend.assert_not_called()
    assert not await get_payments(wallet_id=wallet.id)


async def test_fiat_provider_allowlist_applies_to_existing_wallet(
    client, from_wallet, settings, mocker
):
    wallet = await create_wallet(user_id=from_wallet.user, wallet_type=WalletType.FIAT)
    settings.lnbits_allow_fiat_wallets = True
    settings.stripe_enabled = True
    settings.stripe_limits.allowed_users = [uuid4().hex]
    provider = mocker.patch("lnbits.core.services.payments.get_fiat_provider")
    response = await client.post(
        "/api/v1/payments",
        headers={"X-Api-Key": wallet.inkey},
        json={"out": False, "amount": 5, "unit": "USD", "fiat_provider": "stripe"},
    )
    assert response.status_code == 400
    assert "not available" in response.text
    provider.assert_not_called()
    assert not await get_payments(wallet_id=wallet.id)


async def test_fiat_balances_excluded_from_user_and_server_totals(client, mocker):
    account = Account(id=uuid4().hex)
    await create_account(account)
    lightning = await create_wallet(user_id=account.id)
    fiat = await create_wallet(user_id=account.id, wallet_type=WalletType.FIAT)
    filters = Filters(
        model=AccountFilters,
        filters=[Filter.parse_query("id", [account.id], AccountFilters)],
    )
    initial_total = await get_total_balance()
    await create_payment(
        checking_id=f"internal_{uuid4().hex}",
        data=CreatePayment(
            wallet_id=lightning.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=10000,
            memo="Lightning balance",
        ),
        status=PaymentState.SUCCESS,
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        mocker.AsyncMock(return_value=1000),
    )
    response = await client.post(
        "/api/v1/fiat/cash",
        headers={"X-Api-Key": fiat.adminkey},
        json={"amount": 5, "unit": "USD"},
    )
    assert response.status_code == 201
    cash = Payment.parse_obj(response.json())
    assert cash.is_internal and cash.success
    assert await get_total_balance() == initial_total + 10000
    accounts = await get_accounts(filters=filters)
    assert accounts.total == 1
    assert accounts.data[0].balance_msat == 10000
    assert accounts.data[0].wallet_count == 2
    assert accounts.data[0].transaction_count == 2
    fiat_wallet = await get_wallet(fiat.id)
    assert fiat_wallet and fiat_wallet.balance_msat == cash.amount
    breakdown = await get_wallet_payment_total_breakdown(fiat.id)
    assert len(breakdown) == 1 and breakdown[0].is_fiat
    lightning_breakdown = await get_wallet_payment_total_breakdown(lightning.id)
    assert len(lightning_breakdown) == 1 and not lightning_breakdown[0].is_fiat

    # A user with only an active fiat balance has a zero Lightning balance.
    await delete_wallet(account.id, lightning.id)
    assert await get_total_balance() == initial_total
    accounts = await get_accounts(filters=filters)
    assert accounts.data[0].balance_msat == 0
    assert accounts.data[0].wallet_count == 2
    assert accounts.data[0].transaction_count == 2


@pytest.mark.parametrize("value,expected", [("true", True), ("false", False)])
def test_fiat_wallet_environment_flag(monkeypatch, value, expected):
    monkeypatch.setenv("LNBITS_ALLOW_FIAT_WALLETS", value)
    assert Settings().lnbits_allow_fiat_wallets is expected
