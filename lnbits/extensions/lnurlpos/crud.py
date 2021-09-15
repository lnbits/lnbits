from typing import List, Optional, Union

# from lnbits.db import open_ext_db
from . import db
from .models import lnurlposs

from lnbits.helpers import urlsafe_short_hash

from quart import jsonify


###############lnurlposS##########################


async def create_lnurlpos(
    title: str,
    wallet: Optional[str] = None,
    message: Optional[str] = 0,
    currency: Optional[str] = None,
) -> lnurlposs:
    lnurlpos_id = urlsafe_short_hash()
    lnurlpos_secret = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnurlpos.lnurlposs (
            id,
            secret,
            title,
            wallet,
            message,
            currency
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            lnurlpos_id,
            lnurlpos_secret,
            title,
            wallet,
            message,
            currency
        ),
    )
    return await get_lnurlpos(lnurlpos_id)


async def update_lnurlpos(lnurlpos_id: str, **kwargs) -> Optional[lnurlposs]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnurlpos.lnurlposs SET {q} WHERE id = ?", (*kwargs.values(), lnurlpos_id)
    )
    row = await db.fetchone("SELECT * FROM lnurlpos.lnurlposs WHERE id = ?", (lnurlpos_id,))
    return lnurlposs.from_row(row) if row else None


async def get_lnurlpos(lnurlpos_id: str) -> lnurlposs:
    row = await db.fetchone("SELECT * FROM lnurlpos.lnurlposs WHERE id = ?", (lnurlpos_id,))
    return lnurlposs.from_row(row) if row else None


async def get_lnurlposs(user: str) -> List[lnurlposs]:
    rows = await db.fetchall("""SELECT * FROM lnurlpos.lnurlposs WHERE "user" = ?""", (user,))
    return [lnurlposs.from_row(row) for row in rows]


async def delete_lnurlpos(lnurlpos_id: str) -> None:
    await db.execute("DELETE FROM lnurlpos.lnurlposs WHERE id = ?", (lnurlpos_id,))
