from typing import List, Optional

from . import db
from .models import Admin, Funding
from lnbits.settings import *
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.crud import create_payment
from lnbits.db import Connection


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


async def update_admin(
) -> Optional[Admin]:
    if not CLightningWallet:
        print("poo")
    await db.execute(
        """
        UPDATE admin
        SET user = ?, site_title = ?, site_tagline = ?, site_description = ?, allowed_users = ?, default_wallet_name = ?, data_folder = ?, disabled_ext = ?, force_https = ?, service_fee = ?, funding_source = ?
        WHERE 1
        """,
        (

        ),
    )
    row = await db.fetchone("SELECT * FROM admin WHERE 1")
    return Admin.from_row(row) if row else None

async def update_admin(admin_id: str, **kwargs) -> Optional[Admin]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE jukebox.jukebox SET {q} WHERE id = ?", (*kwargs.values(), juke_id)
    )
    row = await db.fetchone("SELECT * FROM jukebox.jukebox WHERE id = ?", (juke_id,))
    return Jukebox(**row) if row else None

async def get_admin() -> List[Admin]:
    row = await db.fetchone("SELECT * FROM admin WHERE 1")
    return Admin.from_row(row) if row else None


async def get_funding() -> List[Funding]:
    rows = await db.fetchall("SELECT * FROM funding")

    return [Funding.from_row(row) for row in rows]
