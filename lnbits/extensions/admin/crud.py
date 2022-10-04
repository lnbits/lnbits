from typing import List

from lnbits.core.crud import create_payment
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import Settings
from lnbits.tasks import internal_invoice_queue

from . import db


async def update_wallet_balance(wallet_id: str, amount: int) -> str:
    temp_id = f"temp_{urlsafe_short_hash()}"
    internal_id = f"internal_{urlsafe_short_hash()}"

    payment = await create_payment(
        wallet_id=wallet_id,
        checking_id=internal_id,
        payment_request="admin_internal",
        payment_hash="admin_internal",
        amount=amount * 1000,
        memo="Admin top up",
        pending=False,
    )
    # manually send this for now
    await internal_invoice_queue.put(internal_id)


async def update_settings(user: str, **kwargs) -> Settings:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    # print("UPDATE", q)
    await db.execute(f'UPDATE admin.settings SET {q}')
    row = await db.fetchone('SELECT * FROM admin.settings')
    assert row, "Newly updated settings couldn't be retrieved"
    return Settings(**row) if row else None
