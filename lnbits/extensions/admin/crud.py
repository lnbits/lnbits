from typing import List

from lnbits.core.crud import create_payment
from lnbits.helpers import urlsafe_short_hash
from lnbits.tasks import internal_invoice_queue

from . import db
from .models import Admin, Funding


async def update_wallet_balance(wallet_id: str, amount: int) -> str:
    temp_id = f"temp_{urlsafe_short_hash()}"
    internal_id = f"internal_{urlsafe_short_hash()}"
    
    payment = await create_payment(
        wallet_id=wallet_id,
        checking_id=internal_id,
        payment_request="admin_internal",
        payment_hash="admin_internal",
        amount=amount*1000,
        memo="Admin top up",
        pending=False,
    )
    # manually send this for now
    await internal_invoice_queue.put(internal_id)
    return payment

async def update_admin(user: str, **kwargs) -> Admin:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    # print("UPDATE", q)
    await db.execute(
        f'UPDATE admin SET {q} WHERE "user" = ?', (*kwargs.values(), user)
    )
    row = await db.fetchone('SELECT * FROM admin WHERE "user" = ?', (user,))
    assert row, "Newly updated settings couldn't be retrieved"
    return Admin(**row) if row else None

async def get_admin() -> Admin:
    row = await db.fetchone("SELECT * FROM admin")
    return Admin(**row) if row else None

async def update_funding(data: Funding) -> Funding:
    await db.execute(
        """
        UPDATE funding
        SET backend_wallet = ?, endpoint = ?, port = ?, read_key = ?, invoice_key = ?, admin_key = ?, cert = ?, balance = ?, selected = ?
        WHERE id = ?
        """, 
        (data.backend_wallet, data.endpoint, data.port, data.read_key, data.invoice_key, data.admin_key, data.cert, data.balance, data.selected, data.id,),
    )
    row = await db.fetchone('SELECT * FROM funding WHERE "id" = ?', (data.id,))
    assert row, "Newly updated settings couldn't be retrieved"
    return Funding(**row) if row else None

async def get_funding() -> List[Funding]:
    rows = await db.fetchall("SELECT * FROM funding")

    return [Funding(**row) for row in rows]
