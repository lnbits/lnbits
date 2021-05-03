from typing import List, Optional

from . import db
from .models import Jukebox
from lnbits.helpers import urlsafe_short_hash


async def create_jukebox(
    user: str,
    wallet: str,
    title: str,
    price: int,
    sp_user: str,
    sp_secret: str,
    sp_access_token: Optional[str] = "",
    sp_refresh_token: Optional[str] = "",
    sp_device: Optional[str] = "",
    sp_playlists: Optional[str] = "",
) -> Jukebox:
    juke_id = urlsafe_short_hash()
    result = await db.execute(
        """
        INSERT INTO jukebox (id, user, title, wallet, sp_user, sp_secret, sp_access_token, sp_refresh_token, sp_device, sp_playlists, price, profit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            juke_id,
            user,
            title,
            wallet,
            sp_user,
            sp_secret,
            sp_access_token,
            sp_refresh_token,
            sp_device,
            sp_playlists,
            int(price),
            0,
        ),
    )
    jukebox = await get_jukebox(juke_id)
    assert jukebox, "Newly created Jukebox couldn't be retrieved"
    return jukebox


async def update_jukebox(juke_id: str, **kwargs) -> Optional[Jukebox]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE jukebox SET {q} WHERE id = ?", (*kwargs.values(), juke_id)
    )
    row = await db.fetchone("SELECT * FROM jukebox WHERE id = ?", (juke_id,))
    return Jukebox(**row) if row else None


async def get_jukebox(juke_id: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox WHERE id = ?", (juke_id,))
    return Jukebox(**row) if row else None


async def get_jukebox_by_user(user: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox WHERE sp_user = ?", (user,))
    return Jukebox(**row) if row else None


async def get_jukeboxs(user: str) -> List[Jukebox]:
    rows = await db.fetchall("SELECT * FROM jukebox WHERE user = ?", (user,))
    for row in rows:
        if row.sp_playlists == "":
            await delete_jukebox(row.id)
    rows = await db.fetchall("SELECT * FROM jukebox WHERE user = ?", (user,))
    return [Jukebox.from_row(row) for row in rows]


async def delete_jukebox(juke_id: str):
    await db.execute(
        """
        DELETE FROM jukebox WHERE id = ?
        """,
        (juke_id),
    )
