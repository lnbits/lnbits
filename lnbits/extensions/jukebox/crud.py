from typing import List, Optional

from . import db
from .models import Jukebox, JukeboxPayment
from lnbits.helpers import urlsafe_short_hash


async def create_jukebox(
    inkey: str,
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


#####################################PAYMENTS


async def create_jukebox_payment(
    song_id: str, payment_hash: str, juke_id: str
) -> JukeboxPayment:
    result = await db.execute(
        """
        INSERT INTO jukebox_payment (payment_hash, juke_id, song_id, paid)
        VALUES (?, ?, ?, ?)
        """,
        (
            payment_hash,
            juke_id,
            song_id,
            False,
        ),
    )
    jukebox_payment = await get_jukebox_payment(payment_hash)
    assert jukebox_payment, "Newly created Jukebox Payment couldn't be retrieved"
    return jukebox_payment


async def update_jukebox_payment(
    payment_hash: str, **kwargs
) -> Optional[JukeboxPayment]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE jukebox_payment SET {q} WHERE payment_hash = ?",
        (*kwargs.values(), payment_hash),
    )
    return await get_jukebox_payment(payment_hash)


async def get_jukebox_payment(payment_hash: str) -> Optional[JukeboxPayment]:
    row = await db.fetchone(
        "SELECT * FROM jukebox_payment WHERE payment_hash = ?", (payment_hash,)
    )
    return JukeboxPayment(**row) if row else None
