import asyncio
from unittest.mock import AsyncMock

import pytest
from bolt11 import TagChar
from bolt11 import decode as bolt11_decode
from bolt11 import encode as bolt11_encode
from bolt11.types import MilliSatoshi
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_wallet, get_standalone_payment, get_wallet

from lnbits.core.models import Payment, PaymentState, Wallet
from lnbits.core.services import create_invoice, create_user_account, pay_invoice, update_wallet_balance

from lnbits.exceptions import InvoiceError, PaymentError
from lnbits.settings import Settings
from lnbits.tasks import (
    create_permanent_task,
    internal_invoice_listener,
    register_invoice_listener,
)
from lnbits.wallets.base import PaymentResponse
from lnbits.wallets.fake import FakeWallet


@pytest.mark.asyncio
async def test_pay_twice(to_wallet: Wallet):
    _, payment_request = await create_invoice(wallet_id=to_wallet.id, amount=3, memo="Twice")
    await pay_invoice(
        wallet_id=to_wallet.id,
        payment_request=payment_request,
    )
    with pytest.raises(PaymentError, match="Internal invoice already paid."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
        )


@pytest.mark.asyncio
async def test_pay_twice_fast():
    user = await create_user_account()
    wallet_one = await create_wallet(user_id=user.id)
    wallet_two = await create_wallet(user_id=user.id)

    await update_wallet_balance(wallet_one.id, 1000)
    _, pr_a = await create_invoice(wallet_id=wallet_two.id, amount=1000, memo="AAA")
    _, pr_b = await create_invoice(wallet_id=wallet_two.id, amount=1000, memo="BBB")

    print("#### payment_a", pr_a)

    async def pay_first():
        return await pay_invoice(
            wallet_id=wallet_one.id,
            payment_request=pr_a,
        )

    async def pay_second():
        return await pay_invoice(
            wallet_id=wallet_one.id,
            payment_request=pr_b,
        )

    with pytest.raises(PaymentError, match="Insufficient balance."):
        await asyncio.gather(pay_first(), pay_second())

    wallet_one_after = await get_wallet(wallet_one.id)
    assert wallet_one_after
    assert wallet_one_after.balance == 0, "One payment should be deducted."

    wallet_two_after = await get_wallet(wallet_two.id)
    assert wallet_two_after
    assert wallet_two_after.balance == 1000, "One payment received."


@pytest.mark.asyncio
async def test_pay_twice_fast_same_invoice(to_wallet: Wallet):
    _, payment_request = await create_invoice(
        wallet_id=to_wallet.id, amount=3, memo="Twice fast same invoice"
    )

    async def pay_first():
        return await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
        )

    async def pay_second():
        return await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
        )

    with pytest.raises(PaymentError, match="Payment already paid."):
        await asyncio.gather(pay_first(), pay_second())
