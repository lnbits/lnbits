from typing import List, Optional, Union

# from lnbits.db import open_ext_db
from . import db
from .models import Copilots

from lnbits.helpers import urlsafe_short_hash

from quart import jsonify


###############COPILOTS##########################


async def create_copilot(
    title: str,
    user: str,
    lnurl_toggle: Optional[int] = 0,
    wallet: Optional[str] = None,
    animation1: Optional[str] = None,
    animation2: Optional[str] = None,
    animation3: Optional[str] = None,
    animation1threshold: Optional[int] = None,
    animation2threshold: Optional[int] = None,
    animation3threshold: Optional[int] = None,
    animation1webhook: Optional[str] = None,
    animation2webhook: Optional[str] = None,
    animation3webhook: Optional[str] = None,
    lnurl_title: Optional[str] = None,
    show_message: Optional[int] = 0,
    show_ack: Optional[int] = 0,
    show_price: Optional[int] = 0,
    amount_made: Optional[int] = None,
) -> Copilots:
    copilot_id = urlsafe_short_hash()

    await db.execute(
        """
        INSERT INTO copilots (
            id,
            user,
            lnurl_toggle,
            wallet,
            title,
            animation1,
            animation2,
            animation3,
            animation1threshold,
            animation2threshold,
            animation3threshold,
            animation1webhook,
            animation2webhook,
            animation3webhook,
            lnurl_title,
            show_message,
            show_ack,
            show_price,
            lnurl_title,
            amount_made
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            copilot_id,
            user,
            lnurl_toggle,
            wallet,
            title,
            animation1,
            animation2,
            animation3,
            animation1threshold,
            animation2threshold,
            animation3threshold,
            animation1webhook,
            animation2webhook,
            animation3webhook,
            lnurl_title,
            show_message,
            show_ack,
            show_price,
            lnurl_title,
            0,
        ),
    )
    return await get_copilot(copilot_id)


async def update_copilot(copilot_id: str, **kwargs) -> Optional[Copilots]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE copilots SET {q} WHERE id = ?", (*kwargs.values(), copilot_id)
    )
    row = await db.fetchone("SELECT * FROM copilots WHERE id = ?", (copilot_id,))
    return Copilots.from_row(row) if row else None


async def get_copilot(copilot_id: str) -> Copilots:
    row = await db.fetchone("SELECT * FROM copilots WHERE id = ?", (copilot_id,))
    return Copilots.from_row(row) if row else None


async def get_copilots(user: str) -> List[Copilots]:
    rows = await db.fetchall("SELECT * FROM copilots WHERE user = ?", (user,))
    return [Copilots.from_row(row) for row in rows]


async def delete_copilot(copilot_id: str) -> None:
    await db.execute("DELETE FROM copilots WHERE id = ?", (copilot_id,))
