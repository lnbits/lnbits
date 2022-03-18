from typing import List, Optional

from lnbits.core.crud import create_payment
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import *

from . import db
from .models import Admin, Funding


def update_wallet_balance(wallet_id: str, amount: int) -> str:
    temp_id = f"temp_{urlsafe_short_hash()}"
    internal_id = f"internal_{urlsafe_short_hash()}"
    create_payment(
        wallet_id=wallet_id,
        checking_id=internal_id,
        payment_request="admin_internal",
        payment_hash="admin_internal",
        amount=amount * 1000,
        memo="Admin top up",
        pending=False,
    )
    return "success"

async def update_admin(user: str, **kwargs) -> Admin:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    print("UPDATE", q)
    await db.execute(
        f'UPDATE admin SET {q} WHERE "user" = ?', (*kwargs.values(), user)
    )
    row = await db.fetchone('SELECT * FROM admin WHERE "user" = ?', (user,))
    assert row, "Newly updated settings couldn't be retrieved"
    return Admin(**row) if row else None

# async def update_admin(user: str, **kwargs) -> Optional[Admin]:
#     q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
#     await db.execute(
#         f"UPDATE admin SET {q} WHERE user = ?", (*kwargs.values(), user)
#     )
#     new_settings = await get_admin()
#     return new_settings

async def get_admin() -> Admin:
    row = await db.fetchone("SELECT * FROM admin")
    return Admin(**row) if row else None


async def get_funding() -> List[Funding]:
    rows = await db.fetchall("SELECT * FROM funding")

    return [Funding(**row) for row in rows]
