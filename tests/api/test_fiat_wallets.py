import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture

from lnbits.core.crud.payments import (
    create_payment,
    delete_fiat_payment,
    get_payments,
    get_standalone_payment,
    get_wallet_payment_total_breakdown,
    update_payment,
)
from lnbits.core.crud.wallets import (
    create_wallet,
    force_delete_wallet,
    get_total_balance,
    get_wallets,
)
from lnbits.core.db import db
from lnbits.core.models import CreatePayment, PaymentState, Wallet
from lnbits.core.models.payments import CreateInvoice
from lnbits.core.models.wallet_types import WalletType
from lnbits.core.services.fiat_providers import check_fiat_status
from lnbits.core.services.payments import calculate_fiat_amounts, create_fiat_invoice
from lnbits.fiat.base import FiatInvoiceResponse, FiatPaymentStatus
from lnbits.settings import Settings

pytestmark = pytest.mark.anyio


@pytest.fixture
async def cash_wallet(client: AsyncClient, from_wallet: Wallet):
    wallet = await create_wallet(
        user_id=from_wallet.user, wallet_type=WalletType.FIAT, currency="USD"
    )
    yield wallet
    await db.execute("DELETE FROM apipayments WHERE wallet_id = :id", {"id": wallet.id})
    await force_delete_wallet(wallet.id)


async def test_cash_receipt_requires_admin_and_is_retry_safe(
    client: AsyncClient, cash_wallet: Wallet, from_wallet: Wallet, mocker: MockerFixture
):
    convert = mocker.patch(
        "lnbits.core.services.fiat_wallets.fiat_amount_as_satoshis",
        mocker.AsyncMock(return_value=2500),
    )
    notify = mocker.patch(
        "lnbits.task_manager.task_manager.internal_invoice_queue.put_nowait"
    )
    data = {"request_id": str(uuid4()), "amount": "12.34", "unit": "USD"}
    total_before = await get_total_balance()

    for key in (None, cash_wallet.inkey, from_wallet.adminkey):
        response = await client.post(
            "/api/v1/fiat/cash",
            json=data,
            headers={"X-Api-Key": key} if key else {},
        )
        assert response.status_code in (400, 401, 403)
    convert.assert_not_awaited()

    headers = {"X-Api-Key": cash_wallet.adminkey}
    responses = await asyncio.gather(
        *(
            client.post("/api/v1/fiat/cash", json=data, headers=headers)
            for _ in range(3)
        )
    )
    assert all(response.status_code == 200 for response in responses)
    receipt = responses[0].json()
    assert all(r.json()["payment_hash"] == receipt["payment_hash"] for r in responses)
    assert receipt["status"] == "success"
    assert receipt["fee"] == 0
    assert receipt["bolt11"] == ""
    assert receipt["extra"]["wallet_fiat_amount"] == "12.34"
    assert receipt["extra"]["fiat_method"] == "cash"
    assert len(await get_payments(wallet_id=cash_wallet.id)) == 1
    assert await get_total_balance() == total_before
    notify.assert_called_once()

    tamper = await client.patch(
        "/api/v1/payments/extra",
        headers=headers,
        json={
            "payment_hash": receipt["payment_hash"],
            "extra": {"fiat_currency": "USD", "fiat_amount": 99999},
        },
    )
    assert tamper.status_code == 400

    # An ambiguous HTTP failure can be retried without fetching a new FX rate.
    convert.side_effect = RuntimeError("FX unavailable")
    retry = await client.post("/api/v1/fiat/cash", json=data, headers=headers)
    assert retry.status_code == 200
    mismatch = await client.post(
        "/api/v1/fiat/cash", json={**data, "amount": "99"}, headers=headers
    )
    assert mismatch.status_code == 400
    notify.assert_called_once()


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity", "0.000000001"])
async def test_cash_receipt_rejects_invalid_amounts(
    client: AsyncClient, cash_wallet: Wallet, amount: str
):
    response = await client.post(
        "/api/v1/fiat/cash",
        headers={"X-Api-Key": cash_wallet.adminkey},
        json={"request_id": str(uuid4()), "amount": amount, "unit": "USD"},
    )
    assert response.status_code == 400


async def test_cash_receipt_deletion_is_scoped_and_cannot_be_replayed(
    client: AsyncClient, cash_wallet: Wallet, from_wallet: Wallet, mocker: MockerFixture
):
    mocker.patch(
        "lnbits.core.services.fiat_wallets.fiat_amount_as_satoshis",
        mocker.AsyncMock(return_value=1000),
    )
    data = {"request_id": str(uuid4()), "amount": "5", "unit": "USD"}
    headers = {"X-Api-Key": cash_wallet.adminkey}
    response = await client.post("/api/v1/fiat/cash", json=data, headers=headers)
    assert response.status_code == 200
    receipt = response.json()
    url = f"/api/v1/fiat/payments/{receipt['payment_hash']}"
    other_wallet = await create_wallet(
        user_id=from_wallet.user, wallet_type=WalletType.FIAT
    )
    for key, status in (
        (cash_wallet.inkey, 403),
        (from_wallet.adminkey, 403),
        (other_wallet.adminkey, 404),
    ):
        result = await client.delete(url, headers={"X-Api-Key": key})
        assert result.status_code == status

    stale = await get_standalone_payment(receipt["payment_hash"])
    assert stale
    assert (await client.delete(url, headers=headers)).status_code == 200
    assert (await client.delete(url, headers=headers)).status_code == 200
    await update_payment(stale)
    assert await get_payments(wallet_id=cash_wallet.id) == []
    assert await get_wallet_payment_total_breakdown(cash_wallet.id) == []
    retry = await client.post("/api/v1/fiat/cash", json=data, headers=headers)
    assert retry.status_code == 400
    stored = await get_standalone_payment(receipt["payment_hash"])
    assert stored and stored.status == PaymentState.DELETED


async def test_provider_allowlist_overrides_cash_setting(
    client: AsyncClient, cash_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.lnbits_allow_fiat_wallets = True
    settings.stripe_enabled = True
    settings.stripe_limits.allowed_users = [uuid4().hex]
    provider = mocker.patch(
        "lnbits.core.services.payments.get_fiat_provider", mocker.AsyncMock()
    )
    headers = {"X-Api-Key": cash_wallet.adminkey}
    response = await client.post(
        "/api/v1/payments",
        json={
            "out": False,
            "amount": 5,
            "unit": "USD",
            "fiat_provider": "stripe",
            "verified_subscription": True,
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "not available for this user" in response.text
    provider.assert_not_awaited()
    subscription = await client.post(
        "/api/v1/fiat/stripe/subscription",
        json={"subscription_id": "price_test", "quantity": 1, "payment_options": {}},
        headers=headers,
    )
    assert subscription.status_code == 403


async def test_fiat_confirmations_are_atomic_and_deletion_wins_retries(
    cash_wallet: Wallet, mocker: MockerFixture
):
    payment = await create_payment(
        checking_id=f"fiat_stripe_{uuid4().hex}",
        data=CreatePayment(
            wallet_id=cash_wallet.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=10000,
            memo="Provider receipt",
            fiat_provider="stripe",
            extra={"fiat_checking_id": "provider_id"},
        ),
    )
    barrier = asyncio.Event()
    requests = 0

    async def provider_status(checking_id):
        nonlocal requests
        requests += 1
        if requests == 2:
            barrier.set()
        await asyncio.wait_for(barrier.wait(), timeout=5)
        return FiatPaymentStatus(paid=True)

    provider = mocker.Mock()
    provider.get_invoice_status = mocker.AsyncMock(side_effect=provider_status)
    mocker.patch(
        "lnbits.core.services.fiat_providers.get_fiat_provider",
        mocker.AsyncMock(return_value=provider),
    )
    notify = mocker.patch(
        "lnbits.task_manager.task_manager.internal_invoice_queue.put_nowait"
    )
    results = await asyncio.gather(
        check_fiat_status(payment.copy(deep=True)),
        check_fiat_status(payment.copy(deep=True)),
    )
    assert all(result.success for result in results)
    notify.assert_called_once()
    await update_payment(payment)  # A stale pending snapshot must not demote success.
    current = await get_standalone_payment(payment.checking_id)
    assert current and current.success and current.fee == 0

    await delete_fiat_payment(cash_wallet.id, payment.payment_hash)
    assert (await check_fiat_status(payment)).failed
    provider.get_invoice_status.assert_awaited()
    assert provider.get_invoice_status.await_count == 2
    notify.assert_called_once()


async def test_fiat_totals_use_original_amounts_and_include_all_pages(
    cash_wallet: Wallet, mocker: MockerFixture
):
    rate = mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        mocker.AsyncMock(side_effect=AssertionError("Totals must not fetch FX rates")),
    )
    for index in range(1001):
        await create_payment(
            checking_id=f"internal_cash_{uuid4().hex}",
            data=CreatePayment(
                wallet_id=cash_wallet.id,
                payment_hash=uuid4().hex,
                bolt11="",
                amount_msat=(index + 1) * 1000,
                memo="Historical cash",
                extra={"wallet_fiat_currency": "USD", "wallet_fiat_amount": "0.01"},
            ),
            status=PaymentState.SUCCESS,
        )
    for status in (PaymentState.SUCCESS, PaymentState.PENDING, PaymentState.DELETED):
        await create_payment(
            checking_id=f"fiat_stripe_{uuid4().hex}",
            data=CreatePayment(
                wallet_id=cash_wallet.id,
                payment_hash=uuid4().hex,
                bolt11="",
                amount_msat=9000,
                memo="Original provider amount",
                extra={
                    "fiat_currency": "EUR",
                    "fiat_amount": "3.45",
                    "wallet_fiat_currency": "USD",
                    "wallet_fiat_amount": "4.00",
                },
            ),
            status=status,
        )
    totals = await get_wallet_payment_total_breakdown(cash_wallet.id)
    assert len(totals) == 1
    assert totals[0].payments_count == 1002
    assert totals[0].fiat_totals == {"USD": 10.01, "EUR": 3.45}
    rate.assert_not_awaited()


async def test_development_alias_is_filtered_and_excluded_from_lightning_balance(
    cash_wallet: Wallet,
):
    total_before = await get_total_balance()
    await db.execute(
        "UPDATE wallets SET wallet_type = 'receive-only' WHERE id = :id",
        {"id": cash_wallet.id},
    )
    await create_payment(
        checking_id=f"internal_cash_{uuid4().hex}",
        data=CreatePayment(
            wallet_id=cash_wallet.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=50000,
            memo="Cash",
        ),
        status=PaymentState.SUCCESS,
    )
    wallets = await get_wallets(user_id=cash_wallet.user, wallet_type=WalletType.FIAT)
    assert cash_wallet.id in [wallet.id for wallet in wallets]
    assert await get_total_balance() == total_before


@pytest.mark.parametrize("provider_name", ["stripe", "paypal", "square", "revolut"])
async def test_subscription_receipt_creation_is_retry_safe(
    cash_wallet: Wallet, provider_name: str, settings: Settings, mocker: MockerFixture
):
    setattr(settings, f"{provider_name}_enabled", True)
    limits = settings.get_fiat_provider_limits(provider_name)
    assert limits
    limits.allowed_users = []
    limits.service_min_amount_sats = 0
    limits.service_max_amount_sats = 0
    rate = mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        mocker.AsyncMock(return_value=1000),
    )
    receipt_id = uuid4().hex
    provider_id = (
        f"subscription_{receipt_id}" if provider_name == "paypal" else receipt_id
    )
    provider = mocker.Mock()
    provider.create_invoice = mocker.AsyncMock(
        return_value=FiatInvoiceResponse(
            ok=True, checking_id=provider_id, payment_request=""
        )
    )
    mocker.patch(
        "lnbits.core.services.payments.get_fiat_provider",
        mocker.AsyncMock(return_value=provider),
    )
    invoice = CreateInvoice(
        unit="USD",
        amount=5,
        fiat_provider=provider_name,
        extra={
            "fiat_method": "subscription",
            "subscription": {"checking_id": receipt_id},
        },
    )
    receipts = await asyncio.gather(
        *(
            create_fiat_invoice(cash_wallet.id, invoice.copy(deep=True))
            for _ in range(3)
        )
    )
    assert len({receipt.checking_id for receipt in receipts}) == 1
    assert len(await get_payments(wallet_id=cash_wallet.id)) == 1
    assert receipts[0].extra["fiat_checking_id"] == provider_id
    await delete_fiat_payment(cash_wallet.id, receipts[0].payment_hash)
    rate.side_effect = RuntimeError("FX unavailable")
    replay = await create_fiat_invoice(cash_wallet.id, invoice)
    assert replay.status == PaymentState.DELETED
    assert await get_payments(wallet_id=cash_wallet.id) == []


async def test_fiat_amount_metadata_is_set_by_the_server(
    cash_wallet: Wallet, mocker: MockerFixture
):
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        mocker.AsyncMock(return_value=1000),
    )
    _, extra = await calculate_fiat_amounts(
        12.34,
        cash_wallet,
        "USD",
        {"fiat_amount": 999999, "fiat_currency": "EUR"},
    )
    assert extra["fiat_amount"] == 12.34
    assert extra["fiat_currency"] == "USD"


async def test_recheck_fiat_payments_reuses_the_database_connection(
    client: AsyncClient, cash_wallet: Wallet, mocker: MockerFixture
):
    await create_payment(
        checking_id=f"fiat_stripe_{uuid4().hex}",
        data=CreatePayment(
            wallet_id=cash_wallet.id,
            payment_hash=uuid4().hex,
            amount_msat=10000,
            bolt11="",
            memo="Pending provider receipt",
            fiat_provider="stripe",
            extra={"fiat_checking_id": "provider_id"},
        ),
    )
    provider = mocker.Mock()
    provider.get_invoice_status = mocker.AsyncMock(
        return_value=FiatPaymentStatus(paid=True)
    )
    mocker.patch(
        "lnbits.core.services.fiat_providers.get_fiat_provider",
        mocker.AsyncMock(return_value=provider),
    )
    response = await asyncio.wait_for(
        client.get(
            "/api/v1/payments/paginated?recheck_pending=true",
            headers={"X-Api-Key": cash_wallet.adminkey},
        ),
        timeout=5,
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["status"] == "success"


async def test_invoice_key_cannot_supply_a_provider_receipt_id(
    client: AsyncClient, cash_wallet: Wallet, settings: Settings, mocker: MockerFixture
):
    settings.stripe_enabled = True
    settings.stripe_limits.allowed_users = []
    settings.stripe_limits.service_min_amount_sats = 0
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        mocker.AsyncMock(return_value=1000),
    )
    provider_id = uuid4().hex

    async def create_provider_invoice(**kwargs):
        # Simulate the network window before the provider has issued a receipt ID.
        pending = await get_payments(wallet_id=cash_wallet.id)
        assert len(pending) == 1
        assert "fiat_checking_id" not in pending[0].extra
        assert "fiat_payment_request" not in pending[0].extra
        return FiatInvoiceResponse(ok=True, checking_id=provider_id, payment_request="")

    provider = mocker.Mock()
    provider.create_invoice = mocker.AsyncMock(side_effect=create_provider_invoice)
    mocker.patch(
        "lnbits.core.services.payments.get_fiat_provider",
        mocker.AsyncMock(return_value=provider),
    )
    response = await client.post(
        "/api/v1/payments",
        headers={"X-Api-Key": cash_wallet.inkey},
        json={
            "out": False,
            "amount": 5,
            "unit": "USD",
            "fiat_provider": "stripe",
            "extra": {
                "fiat_checking_id": "another_customers_paid_receipt",
                "fiat_payment_request": "https://example.com/forged",
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["extra"]["fiat_checking_id"] == provider_id


async def test_failed_provider_recheck_is_persisted(cash_wallet, mocker):
    from lnbits.core.services.payments import update_pending_payment

    payment = await create_payment(
        checking_id=f"fiat_stripe_{uuid4().hex}",
        data=CreatePayment(
            memo="Test receipt",
            wallet_id=cash_wallet.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=10000,
            fiat_provider="stripe",
            extra={"fiat_checking_id": "cancelled_receipt"},
        ),
    )
    provider = mocker.Mock()
    provider.get_invoice_status = mocker.AsyncMock(
        return_value=FiatPaymentStatus(paid=False)
    )
    mocker.patch(
        "lnbits.core.services.fiat_providers.get_fiat_provider", return_value=provider
    )
    result = await update_pending_payment(payment)
    assert result.failed
    stored = await get_standalone_payment(payment.checking_id)
    assert stored and stored.failed
    assert (await check_fiat_status(payment)).failed
    provider.get_invoice_status.assert_awaited_once()


@pytest.mark.parametrize("provider_name", ["stripe", "paypal", "square"])
async def test_verified_subscription_ignores_new_request_restrictions(
    cash_wallet, settings, mocker, provider_name
):
    from lnbits.core.services.fiat_providers import handle_fiat_payment_confirmation

    setattr(settings, f"{provider_name}_enabled", False)
    settings.get_fiat_provider_limits(provider_name).allowed_users = [uuid4().hex]
    settings.lnbits_max_incoming_payment_amount_sats = 1
    settings.lnbits_wallet_limit_max_balance = 1
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis", return_value=1000
    )
    provider = mocker.patch("lnbits.core.services.payments.get_fiat_provider")
    data = CreateInvoice(
        amount=12.34,
        unit="EUR",
        fiat_provider=provider_name,
        extra={
            "fiat_method": "subscription",
            "subscription": {"checking_id": uuid4().hex},
        },
    )
    payment = await create_fiat_invoice(
        cash_wallet.id, data, verified_subscription=True
    )
    await handle_fiat_payment_confirmation(payment)
    assert payment.success and payment.fee == 0
    assert payment.extra["fiat_currency"] == "EUR"
    assert payment.extra["fiat_amount"] == 12.34
    replay = await create_fiat_invoice(cash_wallet.id, data, verified_subscription=True)
    assert replay.checking_id == payment.checking_id and replay.success
    provider.assert_not_called()
    with pytest.raises(ValueError, match="not enabled"):
        await create_fiat_invoice(cash_wallet.id, data)


async def test_fiat_receipts_do_not_increase_account_balance(cash_wallet, from_wallet):
    from lnbits.core.crud.users import get_accounts
    from lnbits.core.models.users import AccountFilters
    from lnbits.db import Filter, Filters

    filters = Filters(
        model=AccountFilters,
        filters=[Filter.parse_query("wallet_id", [cash_wallet.id], AccountFilters)],
    )
    before = (await get_accounts(filters=filters.copy(deep=True))).data[0].balance_msat
    await create_payment(
        checking_id=f"internal_cash_{uuid4().hex}",
        data=CreatePayment(
            memo="Test receipt",
            wallet_id=cash_wallet.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=123456,
        ),
        status=PaymentState.SUCCESS,
    )
    after = (await get_accounts(filters=filters.copy(deep=True))).data[0].balance_msat
    assert after == before


async def test_confirmed_fiat_receipt_does_not_replay_a_lost_notification(
    cash_wallet, mocker
):
    from lnbits.core.services.fiat_providers import handle_fiat_payment_confirmation

    payment = await create_payment(
        checking_id=f"internal_cash_{uuid4().hex}",
        data=CreatePayment(
            memo="Test receipt",
            wallet_id=cash_wallet.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=1000,
        ),
    )
    notify = mocker.patch(
        "lnbits.task_manager.task_manager.internal_invoice_queue.put_nowait",
        side_effect=RuntimeError("Notification delivery interrupted"),
    )
    with pytest.raises(RuntimeError, match="Notification delivery interrupted"):
        await handle_fiat_payment_confirmation(payment)

    stored = await get_standalone_payment(payment.checking_id)
    assert stored and stored.success
    # Neither a repeated confirmation nor a status recheck republishes the event.
    await handle_fiat_payment_confirmation(payment)
    assert (await check_fiat_status(payment)).success
    notify.assert_called_once()
