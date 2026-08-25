import pytest

from lnbits.core.models import PaymentState
from lnbits.core.services import (
    pay_invoice,
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
    if not is_boltz_wallet:
        assert payment.status == PaymentState.SUCCESS
        assert payment.preimage
    else:
        assert payment.status == PaymentState.PENDING


@pytest.mark.anyio
async def test_services_pay_invoice_0_amount_invoice(
    to_wallet, real_amountless_invoice
):
    with pytest.raises(PaymentError):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=real_amountless_invoice,
        )
