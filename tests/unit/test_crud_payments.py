import pytest

from lnbits.core.crud import create_wallet, get_payments, update_payment
from lnbits.core.models import PaymentState
from lnbits.core.services import create_user_account, update_wallet_balance


async def update_payments(payments):
    # make one of the payments fail
    payment = payments[0]
    payment.status = PaymentState.FAILED
    await update_payment(payment)
    # make one of the payments pending
    payment = payments[1]
    payment.status = PaymentState.PENDING
    await update_payment(payment)


@pytest.mark.anyio
async def test_crud_get_payments(app):

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)

    for _ in range(3):
        await update_wallet_balance(wallet, 10)
        wallet.balance_msat += 10 * 1000
        await update_wallet_balance(wallet, -10)
        wallet.balance_msat += -10 * 1000

    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 6, "should return 6 successful payments"

    payments = await get_payments(wallet_id=wallet.id, incoming=True)
    assert len(payments) == 3, "should return 3 successful incoming payments"
    await update_payments(payments)

    payments = await get_payments(wallet_id=wallet.id, outgoing=True)
    assert len(payments) == 3, "should return 3 successful outgoing payments"
    await update_payments(payments)

    payments = await get_payments(wallet_id=wallet.id, pending=True)
    assert len(payments) == 2, "should return 2 pending payment"

    payments = await get_payments(wallet_id=wallet.id, complete=True, pending=True)
    assert len(payments) == 4, "should return 2 pending and 2 complete payment"

    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 6, "should return all payments"

    payments = await get_payments(wallet_id=wallet.id, complete=True)
    assert len(payments) == 2, "should return 2 successful payment"

    # TODO: both false should return failed payments
    # payments = await get_payments(wallet_id=wallet.id, complete=False, pending=False)
    # assert len(payments) == 2, "should return 2 failed payment"
