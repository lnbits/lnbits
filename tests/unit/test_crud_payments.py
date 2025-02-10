import pytest

from lnbits.core.crud import create_wallet, get_payments, update_payment
from lnbits.core.models import PaymentState
from lnbits.core.services import create_user_account, update_wallet_balance


async def update_payments(payments):
    payments[0].status = PaymentState.FAILED
    await update_payment(payments[0])
    payments[1].status = PaymentState.PENDING
    await update_payment(payments[1])
    payments[2].status = PaymentState.PENDING
    await update_payment(payments[2])


@pytest.mark.anyio
async def test_crud_get_payments(app):

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)

    for _ in range(11):
        await update_wallet_balance(wallet, 10)
        wallet.balance_msat += 10 * 1000
        await update_wallet_balance(wallet, -10)
        wallet.balance_msat += -10 * 1000

    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 22, "should return 22 successful payments"

    payments = await get_payments(wallet_id=wallet.id, incoming=True)
    assert len(payments) == 11, "should return 11 successful incoming payments"
    await update_payments(payments)

    payments = await get_payments(wallet_id=wallet.id, outgoing=True)
    assert len(payments) == 11, "should return 11 successful outgoing payments"
    await update_payments(payments)

    payments = await get_payments(wallet_id=wallet.id, pending=True)
    assert len(payments) == 4, "should return 4 pending payments"

    # function signature should have Optional[bool] for complete and pending to make
    # this distinction possible
    payments = await get_payments(wallet_id=wallet.id, pending=False)
    assert len(payments) == 22, "should return all payments"

    payments = await get_payments(wallet_id=wallet.id, complete=True, pending=True)
    assert len(payments) == 20, "should return 4 pending and 16 complete payments"

    payments = await get_payments(wallet_id=wallet.id, complete=True, outgoing=True)
    assert (
        len(payments) == 10
    ), "should return 8 complete outgoing payments and 2 pending outgoing payments"

    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 22, "should return all payments"

    payments = await get_payments(wallet_id=wallet.id, complete=True)
    assert (
        len(payments) == 18
    ), "should return 14 successful payment and 4 pending payments"

    # both false should return failed payments
    # payments = await get_payments(wallet_id=wallet.id, complete=False, pending=False)
    # assert len(payments) == 2, "should return 2 failed payment"
