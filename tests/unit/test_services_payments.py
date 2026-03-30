from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import (
    create_account,
    create_payment,
    create_wallet,
    get_payment,
    get_payments,
    update_payment,
)
from lnbits.core.models import (
    Account,
    CreateInvoice,
    CreatePayment,
    PaymentState,
    Wallet,
)
from lnbits.core.services.payments import (
    calculate_fiat_amounts,
    cancel_hold_invoice,
    check_payment_status,
    check_pending_payments,
    check_time_limit_between_transactions,
    check_transaction_status,
    check_wallet_limits,
    create_payment_request,
    get_payments_daily_stats,
    settle_hold_invoice,
    update_pending_payment,
    update_pending_payments,
    update_wallet_balance,
)
from lnbits.db import Filters
from lnbits.exceptions import InvoiceError, PaymentError
from lnbits.settings import Settings
from lnbits.wallets.base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentSuccessStatus,
)


@pytest.mark.anyio
async def test_create_payment_request_routes_by_invoice_type(mocker: MockerFixture):
    wallet_payment = SimpleNamespace(checking_id="wallet")
    fiat_payment = SimpleNamespace(checking_id="fiat")
    wallet_mock = mocker.patch(
        "lnbits.core.services.payments.create_wallet_invoice",
        mocker.AsyncMock(return_value=wallet_payment),
    )
    fiat_mock = mocker.patch(
        "lnbits.core.services.payments.create_fiat_invoice",
        mocker.AsyncMock(return_value=fiat_payment),
    )

    assert (
        await create_payment_request("wallet-1", CreateInvoice(amount=1))
        == wallet_payment
    )
    assert (
        await create_payment_request(
            "wallet-1",
            CreateInvoice(amount=1, fiat_provider="stripe"),
        )
        == fiat_payment
    )
    wallet_mock.assert_awaited_once()
    fiat_mock.assert_awaited_once()


@pytest.mark.anyio
async def test_update_pending_payment_and_bulk_pending_updates(mocker: MockerFixture):
    wallet = await _create_wallet()
    failed_id = await _create_payment(wallet)
    success_id = await _create_payment(wallet)
    failed_payment = await get_payment(failed_id)
    success_payment = await get_payment(success_id)

    mocker.patch(
        "lnbits.core.services.payments.check_payment_status",
        mocker.AsyncMock(side_effect=[PaymentFailedStatus(), PaymentSuccessStatus()]),
    )

    await update_pending_payment(failed_payment)
    await update_pending_payment(success_payment)

    assert (await get_payment(failed_id)).status == PaymentState.FAILED
    assert (await get_payment(success_id)).status == PaymentState.SUCCESS

    bulk_wallet = await _create_wallet()
    bulk_failed_id = await _create_payment(bulk_wallet)
    bulk_success_id = await _create_payment(bulk_wallet)
    mocker.patch(
        "lnbits.core.services.payments.check_payment_status",
        mocker.AsyncMock(side_effect=[PaymentFailedStatus(), PaymentSuccessStatus()]),
    )

    await update_pending_payments(bulk_wallet.id)

    bulk_statuses = {
        (await get_payment(bulk_failed_id)).status,
        (await get_payment(bulk_success_id)).status,
    }
    assert bulk_statuses == {PaymentState.FAILED, PaymentState.SUCCESS}


@pytest.mark.anyio
async def test_check_pending_payments_skips_voidwallet_and_updates_recent_items(
    mocker: MockerFixture,
):
    class VoidWallet:
        pass

    class FakeWalletSource:
        pass

    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=VoidWallet(),
    )
    sleep_mock = mocker.patch(
        "lnbits.core.services.payments.asyncio.sleep", mocker.AsyncMock()
    )

    await check_pending_payments()
    sleep_mock.assert_not_awaited()

    existing_pending = await get_payments(pending=True, exclude_uncheckable=True)
    wallet = await _create_wallet()
    checking_id = await _create_payment(wallet)
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=FakeWalletSource(),
    )
    mocker.patch(
        "lnbits.core.services.payments.check_payment_status",
        mocker.AsyncMock(return_value=PaymentSuccessStatus()),
    )

    try:
        await check_pending_payments()
    finally:
        for payment in existing_pending:
            payment.status = PaymentState.PENDING
            await update_payment(payment)

    assert (await get_payment(checking_id)).status == PaymentState.SUCCESS
    assert sleep_mock.await_count >= 1


@pytest.mark.anyio
async def test_update_wallet_balance_validates_credit_and_debit(
    settings: Settings, mocker: MockerFixture
):
    wallet = await _create_wallet()
    wallet.balance_msat = 20_000

    with pytest.raises(ValueError, match="Amount cannot be 0."):
        await update_wallet_balance(wallet, 0)

    with pytest.raises(ValueError, match="can not go into negative balance"):
        await update_wallet_balance(wallet, -30)

    payment_secret = (uuid4().hex * 2)[:64]
    payment_hash = (uuid4().hex * 2)[:64]
    mocker.patch(
        "lnbits.core.services.payments.random_secret_and_hash",
        return_value=(payment_secret, payment_hash),
    )
    mocker.patch(
        "lnbits.core.services.payments.fake_privkey",
        return_value="privkey",
    )
    mocker.patch(
        "lnbits.core.services.payments.bolt11_encode",
        return_value="encoded-bolt11",
    )

    await update_wallet_balance(wallet, -10)

    debit_payment = await get_payment("internal_" + payment_hash)
    assert debit_payment is not None
    assert debit_payment.amount == -10_000
    assert debit_payment.status == PaymentState.SUCCESS

    original_max_balance = settings.lnbits_wallet_limit_max_balance
    try:
        settings.lnbits_wallet_limit_max_balance = 21
        with pytest.raises(ValueError, match="amount exceeds maximum balance"):
            await update_wallet_balance(wallet, 5)

        settings.lnbits_wallet_limit_max_balance = 0
        queue_mock = mocker.patch(
            "lnbits.tasks.internal_invoice_queue_put",
            mocker.AsyncMock(),
        )

        await update_wallet_balance(wallet, 5)
    finally:
        settings.lnbits_wallet_limit_max_balance = original_max_balance

    credit_payments = [
        payment
        for payment in await get_payments(wallet_id=wallet.id, incoming=True)
        if payment.memo == "Admin credit"
    ]
    assert credit_payments
    assert credit_payments[0].status == PaymentState.SUCCESS
    queue_mock.assert_awaited_once_with(credit_payments[0].checking_id)


@pytest.mark.anyio
async def test_check_wallet_limits_and_time_limit(
    settings: Settings, mocker: MockerFixture
):
    time_limit_mock = mocker.patch(
        "lnbits.core.services.payments.check_time_limit_between_transactions",
        mocker.AsyncMock(),
    )
    daily_limit_mock = mocker.patch(
        "lnbits.core.services.payments.check_wallet_daily_withdraw_limit",
        mocker.AsyncMock(),
    )

    await check_wallet_limits("wallet-1", 1_000)

    time_limit_mock.assert_awaited_once_with("wallet-1", None)
    daily_limit_mock.assert_awaited_once_with("wallet-1", 1_000, None)

    wallet = await _create_wallet()
    await _create_payment(wallet, amount_msat=-2_000)
    original_limit = settings.lnbits_wallet_limit_secs_between_trans
    try:
        settings.lnbits_wallet_limit_secs_between_trans = 30
        with pytest.raises(PaymentError) as exc_info:
            await check_time_limit_between_transactions(wallet.id)
        assert "30 seconds between payments" in exc_info.value.message

        other_wallet = await _create_wallet()
        assert await check_time_limit_between_transactions(other_wallet.id) is None
    finally:
        settings.lnbits_wallet_limit_secs_between_trans = original_limit


@pytest.mark.anyio
async def test_calculate_fiat_amounts_handles_conversion_and_errors(
    mocker: MockerFixture,
):
    wallet = await _create_wallet()
    wallet.currency = "EUR"
    mocker.patch(
        "lnbits.core.services.payments.fiat_amount_as_satoshis",
        mocker.AsyncMock(return_value=200),
    )
    sat_to_fiat_mock = mocker.patch(
        "lnbits.core.services.payments.satoshis_amount_as_fiat",
        mocker.AsyncMock(return_value=1.5),
    )

    amount_sat, fiat_amounts = await calculate_fiat_amounts(2.0, wallet, "USD")

    assert amount_sat == 200
    assert fiat_amounts["fiat_currency"] == "USD"
    assert fiat_amounts["wallet_fiat_currency"] == "EUR"
    assert fiat_amounts["wallet_fiat_amount"] == 1.5

    sat_to_fiat_mock.side_effect = Exception("boom")
    amount_sat, fiat_amounts = await calculate_fiat_amounts(10, wallet, "sat", extra={})

    assert amount_sat == 10
    assert fiat_amounts == {}


@pytest.mark.anyio
async def test_check_transaction_status_and_payment_status(mocker: MockerFixture):
    wallet = await _create_wallet()
    missing_hash = uuid4().hex
    assert (await check_transaction_status(wallet.id, missing_hash)).pending is True

    success_hash = uuid4().hex
    success_id = await _create_payment(
        wallet,
        status=PaymentState.SUCCESS,
        payment_hash=success_hash,
        fee=-123,
    )
    success_status = await check_transaction_status(wallet.id, success_hash)
    assert success_status.success is True
    assert success_status.fee_msat == -123

    pending_hash = uuid4().hex
    await _create_payment(wallet, payment_hash=pending_hash)
    mocker.patch(
        "lnbits.core.services.payments.check_payment_status",
        mocker.AsyncMock(return_value=PaymentFailedStatus()),
    )
    assert (await check_transaction_status(wallet.id, pending_hash)).failed is True

    internal_success = await get_payment(success_id)
    internal_success.checking_id = "internal_" + internal_success.payment_hash
    internal_success.status = PaymentState.SUCCESS.value
    assert (await check_payment_status(internal_success)).success is True

    internal_failed = await get_payment(success_id)
    internal_failed.checking_id = "internal_" + internal_failed.payment_hash
    internal_failed.status = PaymentState.FAILED.value
    assert (await check_payment_status(internal_failed)).failed is True

    internal_fiat = await get_payment(success_id)
    internal_fiat.checking_id = "fiat_" + internal_fiat.payment_hash
    internal_fiat.status = PaymentState.PENDING.value
    internal_fiat.fiat_provider = "stripe"
    mocker.patch(
        "lnbits.core.services.payments.check_fiat_status",
        mocker.AsyncMock(return_value=SimpleNamespace(paid=True)),
    )
    assert (await check_payment_status(internal_fiat)).success is True

    outgoing = await get_payment(success_id)
    outgoing.checking_id = "external-out"
    outgoing.amount = -2_000
    incoming = await get_payment(success_id)
    incoming.checking_id = "external-in"
    incoming.amount = 2_000
    funding_source = SimpleNamespace(
        get_payment_status=mocker.AsyncMock(return_value=PaymentSuccessStatus()),
        get_invoice_status=mocker.AsyncMock(return_value=PaymentPendingStatus()),
    )
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=funding_source,
    )

    assert (await check_payment_status(outgoing)).success is True
    assert (await check_payment_status(incoming)).pending is True


@pytest.mark.anyio
async def test_get_payments_daily_stats_fills_missing_dates():
    wallet = await _create_wallet()
    user_id = wallet.user
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    await _create_payment(
        wallet,
        amount_msat=2_000,
        status=PaymentState.SUCCESS,
        time=now - timedelta(days=2),
    )
    await _create_payment(
        wallet,
        amount_msat=-500,
        status=PaymentState.SUCCESS,
        fee=100,
        time=now,
    )

    stats = await get_payments_daily_stats(Filters(), user_id=user_id)

    assert [point.date.date() for point in stats[-3:]] == [
        (now - timedelta(days=2)).date(),
        (now - timedelta(days=1)).date(),
        now.date(),
    ]
    assert [point.balance for point in stats[-3:]] == [2, 2, 1]
    assert stats[-1].fee == 0


@pytest.mark.anyio
async def test_settle_and_cancel_hold_invoice_persist_status(mocker: MockerFixture):
    wallet = await _create_wallet()
    checking_id = await _create_payment(wallet, payment_hash="33" * 32)
    payment = await get_payment(checking_id)
    funding_source = SimpleNamespace(
        settle_hold_invoice=mocker.AsyncMock(
            return_value=InvoiceResponse(ok=True, checking_id="settled")
        ),
        cancel_hold_invoice=mocker.AsyncMock(
            return_value=InvoiceResponse(ok=True, checking_id="cancelled")
        ),
    )
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=funding_source,
    )
    mocker.patch(
        "lnbits.core.services.payments.verify_preimage",
        return_value=False,
    )

    with pytest.raises(InvoiceError, match="Invalid preimage."):
        await settle_hold_invoice(payment, "00" * 32)

    mocker.patch(
        "lnbits.core.services.payments.verify_preimage",
        return_value=True,
    )

    assert (await settle_hold_invoice(payment, "11" * 32)).ok is True
    assert (await cancel_hold_invoice(payment)).ok is True

    stored = await get_payment(checking_id)
    assert stored.preimage == "11" * 32
    assert stored.extra["hold_invoice_settled"] is True
    assert stored.extra["hold_invoice_cancelled"] is True
    assert stored.status == PaymentState.FAILED


def _account() -> Account:
    account_id = uuid4().hex
    return Account(id=account_id, username=f"user_{account_id[:8]}")


async def _create_wallet() -> Wallet:
    account = _account()
    await create_account(account)
    return await create_wallet(
        user_id=account.id, wallet_name=f"wallet_{account.id[:8]}"
    )


async def _create_payment(
    wallet: Wallet,
    *,
    amount_msat: int = 2_000,
    status: PaymentState = PaymentState.PENDING,
    checking_id: str | None = None,
    payment_hash: str | None = None,
    fee: int = 0,
    time: datetime | None = None,
) -> str:
    checking_id = checking_id or f"checking_{uuid4().hex[:8]}"
    payment_hash = payment_hash or uuid4().hex
    payment = await create_payment(
        checking_id=checking_id,
        data=CreatePayment(
            wallet_id=wallet.id,
            payment_hash=payment_hash,
            bolt11=f"bolt11-{checking_id}",
            amount_msat=amount_msat,
            memo="memo",
            fee=fee,
        ),
        status=status,
    )
    if time:
        payment.time = time
        payment.created_at = time
        payment.updated_at = time
        await update_payment(payment)
    return checking_id
