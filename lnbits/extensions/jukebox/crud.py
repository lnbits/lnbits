from typing import List, Optional

from . import db
from .models import Jukebox
from lnbits.helpers import urlsafe_short_hash


async def create_jukebox(
    wallet: str,
    title: str,
    price: int,
    sp_user: str,
    sp_secret: str,
    sp_token: Optional[str] = "",
    sp_device: Optional[str] = "",
    sp_playlists: Optional[str] = "",
) -> Jukebox:
    juke_id = urlsafe_short_hash()
    result = await db.execute(
        """
        INSERT INTO jukebox (id, title, wallet, sp_user, sp_secret, sp_token, sp_device, sp_playlists, price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            juke_id,
            title,
            wallet,
            sp_user,
            sp_secret,
            sp_token,
            sp_device,
            sp_playlists,
            int(price),
        ),
    )
    jukebox = await get_jukebox(juke_id)
    assert jukebox, "Newly created Jukebox couldn't be retrieved"
    return jukebox

async def update_jukebox(sp_user: str, **kwargs) -> Optional[Jukebox]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE jukebox SET {q} WHERE sp_user = ?", (*kwargs.values(), sp_user)
    )
    row = await db.fetchone("SELECT * FROM jukebox WHERE sp_user = ?", (sp_user,))
    return Jukebox(**row) if row else None


async def get_jukebox(id: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox WHERE id = ?", (id,))
    return Jukebox(**row) if row else None


async def get_jukebox_by_user(user: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox WHERE sp_user = ?", (user,))
    return Jukebox(**row) if row else None


async def get_jukeboxs(id: str) -> Optional[Jukebox]:
    rows = await db.fetchone("SELECT * FROM jukebox WHERE id = ?", (id,))
    return [Jukebox(**row) for row in rows]


async def delete_jukebox(shop: int, item_id: int):
    await db.execute(
        """
        DELETE FROM jukebox WHERE id = ?
        """,
        (Jukebox, item_id),
    )
