from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Copilots, CreateCopilotData

###############COPILOTS##########################


async def create_copilot(
    data: CreateCopilotData, inkey: Optional[str] = ""
) -> Optional[Copilots]:
    copilot_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO copilot.newer_copilots (
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
            fullscreen_cam,
            iframe_url,
            amount_made
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            copilot_id,
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
            None,
            0,
        ),
    )
    return await get_copilot(copilot_id)


async def update_copilot(
    data: CreateCopilotData, copilot_id: Optional[str] = ""
) -> Optional[Copilots]:
    q = ", ".join([f"{field[0]} = ?" for field in data])
    items = [f"{field[1]}" for field in data]
    if copilot_id:
        items.append(copilot_id)
    await db.execute(f"UPDATE copilot.newer_copilots SET {q} WHERE id = ?", (items,))
    row = await db.fetchone(
        "SELECT * FROM copilot.newer_copilots WHERE id = ?", (copilot_id,)
    )
    return Copilots(**row) if row else None


async def get_copilot(copilot_id: str) -> Optional[Copilots]:
    row = await db.fetchone(
        "SELECT * FROM copilot.newer_copilots WHERE id = ?", (copilot_id,)
    )
    return Copilots(**row) if row else None


async def get_copilots(user: str) -> List[Copilots]:
    rows = await db.fetchall(
        'SELECT * FROM copilot.newer_copilots WHERE "user" = ?', (user,)
    )
    return [Copilots(**row) for row in rows]


async def delete_copilot(copilot_id: str) -> None:
    await db.execute("DELETE FROM copilot.newer_copilots WHERE id = ?", (copilot_id,))
