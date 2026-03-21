from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from lnbits.core.models import Payment, PaymentState
from lnbits.core.services.payments import update_pending_payment


def _make_payment(*, amount: int = 1000, expired: bool = False) -> Payment:
    expiry = datetime.now(timezone.utc) - timedelta(hours=1) if expired else None
    return Payment(
        checking_id="test_checking_id",
        payment_hash="test_hash",
        wallet_id="test_wallet",
        amount=amount,
        fee=0,
        bolt11="lnbc1test",
        status=PaymentState.PENDING,
        expiry=expiry,
    )


@pytest.mark.anyio
@patch("lnbits.core.services.payments.update_payment", new_callable=AsyncMock)
async def test_expired_incoming_invoice_marked_as_failed(mock_update):
    """Expired incoming invoices should be marked as failed immediately."""
    payment = _make_payment(amount=1000, expired=True)

    result = await update_pending_payment(payment)

    assert result.status == PaymentState.FAILED
    mock_update.assert_called_once_with(payment, conn=None)


@pytest.mark.anyio
@patch("lnbits.core.services.payments.update_payment", new_callable=AsyncMock)
async def test_expired_incoming_skips_backend_check(mock_update):
    """Expired incoming invoices should NOT call check_payment_status."""
    payment = _make_payment(amount=1000, expired=True)

    with patch(
        "lnbits.core.services.payments.check_payment_status"
    ) as mock_check:
        await update_pending_payment(payment)
        mock_check.assert_not_called()


@pytest.mark.anyio
@patch("lnbits.core.services.payments.update_payment", new_callable=AsyncMock)
@patch("lnbits.core.services.payments.check_payment_status", new_callable=AsyncMock)
async def test_expired_outgoing_still_checks_backend(mock_check, mock_update):
    """Expired outgoing payments should still go through normal flow."""
    payment = _make_payment(amount=-1000, expired=True)
    mock_check.return_value = AsyncMock(failed=False, success=False)

    await update_pending_payment(payment)

    mock_check.assert_called_once_with(payment)


@pytest.mark.anyio
@patch("lnbits.core.services.payments.update_payment", new_callable=AsyncMock)
@patch("lnbits.core.services.payments.check_payment_status", new_callable=AsyncMock)
async def test_non_expired_incoming_checks_backend(mock_check, mock_update):
    """Non-expired incoming payments should go through normal backend check."""
    payment = _make_payment(amount=1000, expired=False)
    mock_check.return_value = AsyncMock(failed=False, success=False)

    await update_pending_payment(payment)

    mock_check.assert_called_once_with(payment)
