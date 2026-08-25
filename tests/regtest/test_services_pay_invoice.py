import asyncio

import pytest

from lnbits.core.models import Payment, PaymentState
from lnbits.core.services import (
    pay_invoice,
    update_pending_payment,
)
from lnbits.exceptions import PaymentError

from .helpers import is_boltz_wallet

description = "test pay invoice"


@pytest.mark.anyio
async def test_services_pay_invoice(to_wallet, real_invoice):
    payment = await pay_invoice(
        wallet_id=to_wallet.id,
        payment_request=real_invoice.get("bolt11"),
        description=description,
    )
    assert payment
    assert payment.memo == description
    if is_boltz_wallet and payment.pending:
        payment = await _wait_for_payment_success(payment)
    assert payment.status == PaymentState.SUCCESS
    assert payment.preimage


@pytest.mark.anyio
async def test_services_pay_invoice_0_amount_invoice(
    to_wallet, real_amountless_invoice
):
    with pytest.raises(PaymentError):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=real_amountless_invoice,
        )


async def _wait_for_payment_success(payment: Payment, timeout: float = 30) -> Payment:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        payment = await update_pending_payment(payment)
        if payment.success:
            return payment
        if payment.failed:
            raise AssertionError(f"Payment '{payment.payment_hash}' failed.")
        await asyncio.sleep(0.25)

    raise AssertionError(
        f"Payment '{payment.payment_hash}' did not succeed within {timeout}s. "
        f"Last status: '{payment.status}'."
    )
