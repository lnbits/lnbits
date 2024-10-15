import pytest

from lnbits.core.models import Wallet
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.exceptions import PaymentError


@pytest.mark.asyncio
async def test_invalid_bolt11(to_wallet):
    with pytest.raises(PaymentError):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request="lnbcr1123123n",
        )


@pytest.mark.asyncio
async def test_amountless_invoice(to_wallet: Wallet):
    zero_amount_invoice = (
        "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
        "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
        "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
        "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
        "6hjxepwp93cq398l3s"
    )
    with pytest.raises(PaymentError, match="Amountless invoices not supported."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=zero_amount_invoice,
        )


@pytest.mark.asyncio
async def test_payment_limit(to_wallet: Wallet):
    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=101, memo=""
    )
    with pytest.raises(PaymentError, match="Amount in invoice is too high."):

        await pay_invoice(
            wallet_id=to_wallet.id,
            max_sat=100,
            payment_request=payment_request,
        )
