import pytest

from lnbits.core.models import PaymentState
from lnbits.core.services import (
    pay_invoice,
)
from lnbits.exceptions import PaymentError

description = "test pay invoice"


@pytest.mark.anyio
async def test_services_pay_invoice(to_wallet, real_invoice):
    payment = await pay_invoice(
        wallet_id=to_wallet.id,
        payment_request=real_invoice.get("bolt11"),
        description=description,
    )
    assert payment
    assert payment.status == PaymentState.SUCCESS
    assert payment.memo == description
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
