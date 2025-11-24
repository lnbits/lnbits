import pytest

from lnbits.core.crud import (
    create_wallet,
    get_payments,
    get_payments_paginated,
    update_payment,
)
from lnbits.core.models import PaymentFilters, PaymentState
from lnbits.core.services import (
    create_invoice,
    create_user_account,
    update_wallet_balance,
)
from lnbits.db import Filters


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

    filters = Filters(limit=100)
    payments = await get_payments(wallet_id=wallet.id, filters=filters)
    assert len(payments) == 22, "should return 22 successful payments"

    payments = await get_payments(wallet_id=wallet.id, incoming=True, filters=filters)
    assert len(payments) == 11, "should return 11 successful incoming payments"
    await update_payments(payments)

    payments = await get_payments(wallet_id=wallet.id, outgoing=True, filters=filters)
    assert len(payments) == 11, "should return 11 successful outgoing payments"
    await update_payments(payments)

    payments = await get_payments(wallet_id=wallet.id, pending=True, filters=filters)
    assert len(payments) == 4, "should return 4 pending payments"

    # function signature should have Optional[bool] for complete and pending to make
    # this distinction possible
    payments = await get_payments(wallet_id=wallet.id, pending=False, filters=filters)
    assert len(payments) == 22, "should return all payments"

    payments = await get_payments(
        wallet_id=wallet.id, complete=True, pending=True, filters=filters
    )
    assert len(payments) == 20, "should return 4 pending and 16 complete payments"

    payments = await get_payments(
        wallet_id=wallet.id, complete=True, outgoing=True, filters=filters
    )
    assert (
        len(payments) == 10
    ), "should return 8 complete outgoing payments and 2 pending outgoing payments"

    payments = await get_payments(wallet_id=wallet.id, filters=filters)
    assert len(payments) == 22, "should return all payments"

    payments = await get_payments(wallet_id=wallet.id, complete=True, filters=filters)
    assert (
        len(payments) == 18
    ), "should return 14 successful payment and 4 pending payments"

    # both false should return failed payments
    # payments = await get_payments(wallet_id=wallet.id, complete=False, pending=False)
    # assert len(payments) == 2, "should return 2 failed payment"


@pytest.mark.anyio
async def test_crud_search_payments():

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    filters = Filters(
        search="",
        model=PaymentFilters,
    )
    # no memo
    await create_invoice(wallet_id=wallet.id, amount=30, memo="")
    await create_invoice(wallet_id=wallet.id, amount=30, memo="Invoice A")
    filters.search = "Invoice A"
    page = await get_payments_paginated(
        wallet_id=wallet.id,
        filters=filters,
    )
    assert page.total == 1, "should return only Invoice A"

    filters.search = "Invoice B"
    page = await get_payments_paginated(
        wallet_id=wallet.id,
        filters=filters,
    )
    assert page.total == 0, "no Invoice B yet"

    for i in range(15):
        await create_invoice(wallet_id=wallet.id, amount=30 + i, memo="Invoice A")
        await create_invoice(wallet_id=wallet.id, amount=30 + i, memo="Invoice B")

    filters.search = None
    page = await get_payments_paginated(
        wallet_id=wallet.id,
        filters=filters,
    )
    assert page.total == 32, "should return all payments"

    filters.search = "Invoice A"
    page = await get_payments_paginated(
        wallet_id=wallet.id,
        filters=filters,
    )
    assert page.total == 16

    filters.search = "Invoice B"
    page = await get_payments_paginated(
        wallet_id=wallet.id,
        filters=filters,
    )
    assert page.total == 15

    filters.search = "Invoice"
    page = await get_payments_paginated(
        wallet_id=wallet.id,
        filters=filters,
    )
    assert page.total == 31
