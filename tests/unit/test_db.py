from datetime import date, timezone

import pytest

from lnbits.core.crud import (
    create_wallet,
    delete_wallet,
    get_wallet,
    get_wallet_for_key,
)
from lnbits.core.crud.payments import get_payment
from lnbits.core.models import CreateInvoice
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.db import POSTGRES


@pytest.mark.anyio
async def test_date_conversion(db):
    if db.type == POSTGRES:
        row = await db.fetchone("SELECT now()::date as now")
        assert row and isinstance(row.get("now"), date)


@pytest.mark.anyio
async def test_payment_datetime_fields_have_timezone(app, to_user):
    """Test that Payment datetime fields always have UTC timezone info."""
    wallet = await create_wallet(user_id=to_user.id, wallet_name="test_tz_wallet")
    invoice_data = CreateInvoice(amount=10, memo="timezone_test", out=False)
    invoice = await create_wallet_invoice(wallet.id, invoice_data)

    payment = await get_payment(invoice.checking_id)
    assert payment is not None

    # All datetime fields should have UTC timezone info
    assert payment.time.tzinfo == timezone.utc
    assert payment.created_at.tzinfo == timezone.utc
    assert payment.updated_at.tzinfo == timezone.utc
    if payment.expiry:
        assert payment.expiry.tzinfo == timezone.utc


# make test to create wallet and delete wallet
@pytest.mark.anyio
async def test_create_wallet_and_delete_wallet(app, to_user):
    # create wallet
    wallet = await create_wallet(user_id=to_user.id, wallet_name="test_wallet_delete")
    assert wallet

    # delete wallet
    await delete_wallet(user_id=to_user.id, wallet_id=wallet.id)

    # check if wallet is deleted
    del_wallet = await get_wallet(wallet.id)
    assert del_wallet is None

    # check if wallet is deleted
    del_wallet = await get_wallet(wallet.id, False)
    assert del_wallet is None

    del_wallet = await get_wallet(wallet.id, None)
    assert del_wallet is not None
    assert del_wallet.deleted is True

    del_wallet = await get_wallet(wallet.id, True)
    assert del_wallet is not None
    assert del_wallet.deleted is True

    del_wallet = await get_wallet_for_key(wallet.inkey)
    assert del_wallet is None
