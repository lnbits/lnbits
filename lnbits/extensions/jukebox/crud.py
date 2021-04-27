from typing import List, Optional

from . import db
from .wordlists import animals
from .models import Shop, Item


async def create_update_jukebox(wallet_id: str) -> int:
    juke_id = urlsafe_short_hash()
    result = await db.execute(
        """
        INSERT INTO jukebox (id, wallet, user, secret, token, playlists)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (juke_id, wallet_id, "", "", "", ""),
    )
    return result._result_proxy.lastrowid


async def get_jukebox(id: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox WHERE id = ?", (id,))
    return Shop(**dict(row)) if row else None

async def get_jukeboxs(id: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox WHERE id = ?", (id,))
    return Shop(**dict(row)) if row else None

async def delete_jukebox(shop: int, item_id: int):
    await db.execute(
        """
        DELETE FROM jukebox WHERE id = ?
        """,
        (shop, item_id),
    )
