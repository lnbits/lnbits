import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from lnbits.core.crud import create_wallet, get_standalone_payment, get_wallet
from lnbits.core.crud.payments import (
    create_payment,
    get_payments_paginated,
    update_payment,
)
from lnbits.core.models import CreatePayment, PaymentState
from lnbits.core.services.payments import pay_invoice
from lnbits.exceptions import PaymentError
from lnbits.wallets.base import (
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentSuccessStatus,
)


@pytest.fixture
async def resend_context(
    app, from_user, settings, external_funding_source, mocker, request
):
    wallet = await create_wallet(user_id=from_user.id)
    fee_wallet = await create_wallet(user_id=from_user.id)
    settings.lnbits_reserve_fee_min = 20_000
    settings.lnbits_service_fee = 1
    settings.lnbits_service_fee_max = 0
    settings.lnbits_service_fee_wallet = fee_wallet.id
    available_balance = getattr(request, "param", 30_000)
    await _credit_wallet(wallet.id, 1_030_000 + available_balance)
    invoice = await external_funding_source.create_invoice(1_000)
    payment = await create_payment(
        f"backend_{invoice.checking_id}",
        CreatePayment(
            wallet_id=wallet.id,
            payment_hash=invoice.checking_id,
            bolt11=invoice.payment_request,
            amount_msat=-1_000_000,
            fee=-30_000,
            memo="Original memo",
            extra={"reference": "order-1"},
            labels=["original"],
            external_id="order-1",
            webhook="https://example.com/payment",
        ),
    )
    payment = await get_standalone_payment(payment.checking_id, wallet_id=wallet.id)
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=external_funding_source,
    )
    backend = mocker.patch.object(
        external_funding_source,
        "pay_invoice",
        AsyncMock(return_value=PaymentResponse()),
    )
    status = mocker.patch.object(
        external_funding_source,
        "get_payment_status",
        AsyncMock(return_value=PaymentPendingStatus()),
    )
    notify = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background"
    )
    return SimpleNamespace(
        wallet=wallet,
        fee_wallet=fee_wallet,
        payment=payment,
        invoice=invoice,
        backend=backend,
        status=status,
        notify=notify,
        available_balance=available_balance,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("success", [False, True], ids=["pending", "success"])
async def test_force_resend_reuses_payment_without_another_debit(
    resend_context, success
):
    ctx = resend_context
    before = ctx.payment
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance
    ctx.backend.return_value = PaymentResponse(
        ok=True if success else None,
        checking_id=f"resent_{before.payment_hash}",
        fee_msat=2_000 if success else None,
        preimage=ctx.invoice.preimage if success else None,
    )

    payment = await pay_invoice(
        wallet_id=ctx.wallet.id, payment_request=before.bolt11, force_resend=True
    )

    ctx.backend.assert_awaited_once_with(before.bolt11, 20_000)
    ctx.status.assert_not_awaited()
    outgoing = await get_payments_paginated(wallet_id=ctx.wallet.id, outgoing=True)
    assert outgoing.total == 1
    stored = outgoing.data[0]
    assert stored.checking_id == payment.checking_id == f"resent_{before.payment_hash}"
    for field in (
        "payment_hash",
        "wallet_id",
        "amount",
        "bolt11",
        "memo",
        "extra",
        "labels",
        "external_id",
        "webhook",
        "created_at",
    ):
        assert getattr(stored, field) == getattr(before, field)
    assert stored.status == (PaymentState.SUCCESS if success else PaymentState.PENDING)
    assert stored.fee == (-12_000 if success else -30_000)
    assert stored.preimage == (ctx.invoice.preimage if success else None)
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance + (
        18_000 if success else 0
    )
    assert await _wallet_balance(ctx.fee_wallet.id) == (10_000 if success else 0)
    assert ctx.notify.call_count == int(success)

    if success:
        with pytest.raises(PaymentError):
            await pay_invoice(
                wallet_id=ctx.wallet.id,
                payment_request=before.bolt11,
                force_resend=True,
            )
        assert ctx.backend.await_count == 1
        assert ctx.notify.call_count == 1
        fees = await get_payments_paginated(wallet_id=ctx.fee_wallet.id)
        assert fees.total == 1
    else:
        await pay_invoice(
            wallet_id=ctx.wallet.id, payment_request=before.bolt11, force_resend=True
        )
        assert ctx.backend.await_count == 2
        assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance
        assert (
            await get_payments_paginated(wallet_id=ctx.wallet.id, outgoing=True)
        ).total == 1


@pytest.mark.anyio
@pytest.mark.parametrize("resend_context", [0], indirect=True)
@pytest.mark.parametrize(
    "reserve,available,allowed",
    [
        (10_000, 0, False),
        (10_000, 19_999, False),
        (10_000, 20_000, True),
        (20_000, 0, False),
        (20_000, 29_999, False),
        (20_000, 30_000, True),
        (40_000, 0, False),
        (40_000, 20_000, False),
        (40_000, 49_999, False),
        (40_000, 50_000, True),
    ],
)
async def test_force_resend_checks_fee_balance_without_changing_reservation(
    resend_context, settings, reserve, available, allowed
):
    ctx = resend_context
    if available:
        await _credit_wallet(ctx.wallet.id, available)
    settings.lnbits_reserve_fee_min = reserve

    if allowed:
        await pay_invoice(
            wallet_id=ctx.wallet.id,
            payment_request=ctx.payment.bolt11,
            force_resend=True,
        )
        ctx.backend.assert_awaited_once_with(ctx.payment.bolt11, reserve)
    else:
        with pytest.raises(PaymentError, match="You must reserve at least"):
            await pay_invoice(
                wallet_id=ctx.wallet.id,
                payment_request=ctx.payment.bolt11,
                force_resend=True,
            )
        ctx.backend.assert_not_awaited()

    stored = await get_standalone_payment(
        ctx.payment.checking_id, wallet_id=ctx.wallet.id
    )
    assert stored is not None
    assert stored.pending
    assert stored.fee == ctx.payment.fee
    assert await _wallet_balance(ctx.wallet.id) == available
    ctx.notify.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status",
    [
        PaymentPendingStatus(),
        PaymentSuccessStatus(fee_msat=2_000),
        PaymentFailedStatus(),
    ],
    ids=["pending", "success", "failed"],
)
async def test_force_resend_reconciles_rejected_attempt(resend_context, status):
    ctx = resend_context
    ctx.backend.return_value = PaymentResponse(
        ok=False, error_message="Already attempted"
    )
    ctx.status.return_value = status

    if status.failed:
        with pytest.raises(PaymentError, match="Payment failed: Already attempted"):
            await pay_invoice(
                wallet_id=ctx.wallet.id,
                payment_request=ctx.payment.bolt11,
                force_resend=True,
            )
    else:
        result = await pay_invoice(
            wallet_id=ctx.wallet.id,
            payment_request=ctx.payment.bolt11,
            force_resend=True,
        )
        assert result.success == status.success

    ctx.status.assert_awaited_once_with(ctx.payment.checking_id)
    stored = await get_standalone_payment(
        ctx.payment.checking_id, wallet_id=ctx.wallet.id
    )
    assert stored is not None
    assert stored.status == str(status)
    expected_balance = 1_030_000 if status.failed else 18_000 if status.success else 0
    assert (
        await _wallet_balance(ctx.wallet.id) == ctx.available_balance + expected_balance
    )
    assert await _wallet_balance(ctx.fee_wallet.id) == (10_000 if status.success else 0)
    assert ctx.notify.call_count == int(status.success)


@pytest.mark.anyio
async def test_force_resend_status_error_does_not_refund(resend_context):
    ctx = resend_context
    ctx.backend.return_value = PaymentResponse(ok=False)
    ctx.status.side_effect = RuntimeError("Status unavailable")
    with pytest.raises(RuntimeError, match="Status unavailable"):
        await pay_invoice(
            wallet_id=ctx.wallet.id,
            payment_request=ctx.payment.bolt11,
            force_resend=True,
        )
    stored = await get_standalone_payment(
        ctx.payment.checking_id, wallet_id=ctx.wallet.id
    )
    assert stored is not None
    assert stored.pending
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance
    ctx.notify.assert_not_called()


@pytest.mark.anyio
async def test_force_resend_timeout_keeps_reservation(resend_context, settings):
    ctx = resend_context
    settings.lnbits_funding_source_pay_invoice_wait_seconds = 1

    async def hold_payment(*args, **kwargs):
        await asyncio.Event().wait()

    ctx.backend.side_effect = hold_payment
    result = await pay_invoice(
        wallet_id=ctx.wallet.id, payment_request=ctx.payment.bolt11, force_resend=True
    )
    assert result.pending
    assert result.checking_id == ctx.payment.checking_id
    stored = await get_standalone_payment(result.checking_id, wallet_id=ctx.wallet.id)
    assert stored is not None
    assert stored.pending and stored.fee == -30_000
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance
    ctx.status.assert_not_awaited()
    ctx.notify.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("state", [PaymentState.SUCCESS, PaymentState.FAILED])
async def test_force_resend_rejects_settled_payment(resend_context, state):
    ctx = resend_context
    ctx.payment.status = state
    await update_payment(ctx.payment)
    balance_before = await _wallet_balance(ctx.wallet.id)
    with pytest.raises(PaymentError, match="Can only force resend a pending payment"):
        await pay_invoice(
            wallet_id=ctx.wallet.id,
            payment_request=ctx.payment.bolt11,
            force_resend=True,
        )
    ctx.backend.assert_not_awaited()
    assert await _wallet_balance(ctx.wallet.id) == balance_before


@pytest.mark.anyio
@pytest.mark.parametrize("other_wallet", [False, True], ids=["missing", "wrong-wallet"])
async def test_force_resend_requires_existing_payment_in_wallet(
    resend_context, external_funding_source, other_wallet
):
    ctx = resend_context
    wallet_id, bolt11 = ctx.wallet.id, ctx.payment.bolt11
    if other_wallet:
        wallet = await create_wallet(user_id=ctx.wallet.user)
        wallet_id = wallet.id
        await _credit_wallet(wallet_id, 2_000_000)
    else:
        invoice = await external_funding_source.create_invoice(1_000)
        bolt11 = invoice.payment_request
    with pytest.raises(PaymentError, match="No previous payment found to resend"):
        await pay_invoice(
            wallet_id=wallet_id, payment_request=bolt11, force_resend=True
        )
    ctx.backend.assert_not_awaited()
    assert (
        await get_payments_paginated(wallet_id=ctx.wallet.id, outgoing=True)
    ).total == 1


@pytest.mark.anyio
async def test_force_resend_rejects_changed_invoice(
    resend_context, external_funding_source
):
    ctx = resend_context
    original = ctx.payment.bolt11
    other = await external_funding_source.create_invoice(1_000)
    ctx.payment.bolt11 = other.payment_request
    await update_payment(ctx.payment)
    with pytest.raises(PaymentError, match="Invalid invoice. Bolt11 changed."):
        await pay_invoice(
            wallet_id=ctx.wallet.id, payment_request=original, force_resend=True
        )
    ctx.backend.assert_not_awaited()
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance


@pytest.mark.anyio
@pytest.mark.parametrize("force_resend", [False, None])
async def test_pending_payment_requires_explicit_force_resend(
    resend_context, force_resend
):
    ctx = resend_context
    await _credit_wallet(ctx.wallet.id, 2_000_000)
    with pytest.raises(PaymentError, match="Payment is still pending."):
        await pay_invoice(
            wallet_id=ctx.wallet.id,
            payment_request=ctx.payment.bolt11,
            force_resend=force_resend,
        )
    ctx.backend.assert_not_awaited()
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance + 2_000_000


@pytest.mark.anyio
async def test_force_resend_accepts_invoice_case_changes(resend_context):
    ctx = resend_context
    result = await pay_invoice(
        wallet_id=ctx.wallet.id,
        payment_request=ctx.payment.bolt11.upper(),
        force_resend=True,
    )
    assert result.pending
    ctx.backend.assert_awaited_once_with(ctx.payment.bolt11, 20_000)
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance


@pytest.mark.anyio
async def test_concurrent_force_resends_settle_only_once(resend_context):
    ctx = resend_context
    ctx.backend.return_value = PaymentResponse(ok=True, fee_msat=2_000)
    results = await asyncio.gather(
        *[
            pay_invoice(
                wallet_id=ctx.wallet.id,
                payment_request=ctx.payment.bolt11,
                force_resend=True,
            )
            for _ in range(2)
        ],
        return_exceptions=True,
    )
    failures = [result for result in results if isinstance(result, PaymentError)]
    assert len(failures) == 1
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    ctx.backend.assert_awaited_once()
    ctx.notify.assert_called_once()
    assert await _wallet_balance(ctx.wallet.id) == ctx.available_balance + 18_000
    fees = await get_payments_paginated(wallet_id=ctx.fee_wallet.id)
    assert fees.total == 1
    assert fees.data[0].amount == 10_000


async def _credit_wallet(wallet_id, amount_msat):
    await create_payment(
        "internal_" + uuid4().hex,
        CreatePayment(
            wallet_id=wallet_id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=amount_msat,
            memo="Test balance",
        ),
        status=PaymentState.SUCCESS,
    )


async def _wallet_balance(wallet_id: str) -> int:
    wallet = await get_wallet(wallet_id)
    assert wallet is not None
    return wallet.balance_msat
