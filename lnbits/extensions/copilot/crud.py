from typing import List, Optional, Union

from . import db
from .models import Copilots, CreateCopilotData
from lnbits.helpers import urlsafe_short_hash

###############COPILOTS##########################


async def create_copilot(
    data: CreateCopilotData, inkey: Optional[str] = ""
) -> Copilots:
    copilot_id = urlsafe_short_hash()

    await db.execute(
        """
        INSERT INTO copilot.copilots (
            id,
            "user",
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
            amount_made
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.copilot_id,
            data.user,
            int(data.lnurl_toggle),
            data.wallet,
            data.title,
            data.animation1,
            data.animation2,
            data.animation3,
            data.animation1threshold,
            data.animation2threshold,
            data.animation3threshold,
            data.animation1webhook,
            data.animation2webhook,
            data.animation3webhook,
            data.lnurl_title,
            int(data.show_message),
            int(data.show_ack),
            data.show_price,
            0,
        ),
    )
    return await get_copilot(copilot_id)


async def update_copilot(copilot_id: str, **kwargs) -> Optional[Copilots]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE copilot.copilots SET {q} WHERE id = ?", (*kwargs.values(), copilot_id)
    )
    row = await db.fetchone(
        "SELECT * FROM copilot.copilots WHERE id = ?", (copilot_id,)
    )
    return Copilots.from_row(row) if row else None


async def get_copilot(copilot_id: str) -> Copilots:
    row = await db.fetchone(
        "SELECT * FROM copilot.copilots WHERE id = ?", (copilot_id,)
    )
    return Copilots.from_row(row) if row else None


async def get_copilots(user: str) -> List[Copilots]:
    rows = await db.fetchall(
        """SELECT * FROM copilot.copilots WHERE "user" = ?""", (user,)
    )
    return [Copilots.from_row(row) for row in rows]


async def delete_copilot(copilot_id: str) -> None:
    await db.execute("DELETE FROM copilot.copilots WHERE id = ?", (copilot_id,))
