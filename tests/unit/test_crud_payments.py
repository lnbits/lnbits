import pytest

from lnbits.core.crud import create_wallet, get_payments, update_payment
from lnbits.core.models import PaymentState
from lnbits.core.services import create_user_account, update_wallet_balance


@pytest.mark.anyio
async def test_crud_get_payments():

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)

    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 0

    await update_wallet_balance(wallet, 10)
    wallet.balance_msat += 10 * 1000

    payments = await get_payments(wallet_id=wallet.id)
    print(payments)
    assert len(payments) == 1

    await update_wallet_balance(wallet, -10)
    wallet.balance_msat += -10 * 1000

    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 2

    payment = payments[0]
    payment.status = PaymentState.FAILED
    await update_payment(payment)

    # should return no pending payments
    payments = await get_payments(wallet_id=wallet.id, pending=True)
    assert len(payments) == 0

    # default should not return failed payments
    payments = await get_payments(wallet_id=wallet.id)
    assert len(payments) == 1

    # should return only complete payments
    payments = await get_payments(wallet_id=wallet.id, complete=True)
    assert len(payments) == 1

    # should return only failed payments
    # payments = await get_payments(wallet_id=wallet.id, complete=False)
    # assert len(payments) == 1
