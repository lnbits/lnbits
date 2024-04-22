import pytest
from lnbits.core.services import (
    pay_invoice,
)

description = "test pay invoice"

@pytest.mark.asyncio
async def test_services_pay_invoice(to_wallet, real_invoice):
    res = await pay_invoice(wallet_id=to_wallet.id, payment_request=real_invoice, description=description)
