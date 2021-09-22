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
    lnurlpos_key = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnurlpos.lnurlposs (
            id,
            key,
            title,
            wallet,
            message,
            currency
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (lnurlpos_id, lnurlpos_key, title, wallet, message, currency),
    )
    return await get_lnurlpos(lnurlpos_id)


async def update_lnurlpos(lnurlpos_id: str, **kwargs) -> Optional[lnurlposs]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnurlpos.lnurlposs SET {q} WHERE id = ?",
        (*kwargs.values(), lnurlpos_id),
    )
    row = await db.fetchone(
        "SELECT * FROM lnurlpos.lnurlposs WHERE id = ?", (lnurlpos_id,)
    )
    return lnurlposs.from_row(row) if row else None


async def get_lnurlpos(lnurlpos_id: str) -> lnurlposs:
    row = await db.fetchone(
        "SELECT * FROM lnurlpos.lnurlposs WHERE id = ?", (lnurlpos_id,)
    )
    return lnurlposs.from_row(row) if row else None


async def get_lnurlposs(wallet_ids: Union[str, List[str]]) -> List[lnurlposs]:
    wallet_ids = [wallet_ids]
    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM lnurlpos.lnurlposs WHERE wallet IN ({q})
        ORDER BY id
        """,
        (*wallet_ids,),
    )

    return [lnurlposs.from_row(row) for row in rows]


async def delete_lnurlpos(lnurlpos_id: str) -> None:
    await db.execute("DELETE FROM lnurlpos.lnurlposs WHERE id = ?", (lnurlpos_id,))
