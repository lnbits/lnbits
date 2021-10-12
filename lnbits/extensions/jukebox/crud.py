from typing import List, Optional

from . import db
from .models import Jukebox, JukeboxPayment, CreateJukeLinkData
from lnbits.helpers import urlsafe_short_hash


async def create_jukebox(
    data: CreateJukeLinkData,
    inkey: Optional[str] = "",
) -> Jukebox:
    juke_id = urlsafe_short_hash()
    result = await db.execute(
        """
        INSERT INTO jukebox.jukebox (id, user, title, wallet, sp_user, sp_secret, sp_access_token, sp_refresh_token, sp_device, sp_playlists, price, profit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            juke_id,
            data.user,
            data.title,
            data.wallet,
            data.sp_user,
            data.sp_secret,
            data.sp_access_token,
            data.sp_refresh_token,
            data.sp_device,
            data.sp_playlists,
            data.price,
            0,
        ),
    )
    jukebox = await get_jukebox(juke_id)
    assert jukebox, "Newly created Jukebox couldn't be retrieved"
    return jukebox


async def update_jukebox(
    data: CreateJukeLinkData, juke_id: Optional[str] = ""
) -> Optional[Jukebox]:
    q = ", ".join([f"{field[0]} = ?" for field in data])
    items = [f"{field[1]}" for field in data]
    items.append(juke_id)
    print(q)
    print(items)
    await db.execute(f"UPDATE jukebox.jukebox SET {q} WHERE id = ?", (items))
    row = await db.fetchone("SELECT * FROM jukebox.jukebox WHERE id = ?", (juke_id,))
    return Jukebox(**row) if row else None


async def get_jukebox(juke_id: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox.jukebox WHERE id = ?", (juke_id,))
    return Jukebox(**row) if row else None


async def get_jukebox_by_user(user: str) -> Optional[Jukebox]:
    row = await db.fetchone("SELECT * FROM jukebox.jukebox WHERE sp_user = ?", (user,))
    return Jukebox(**row) if row else None


async def get_jukeboxs(user: str) -> List[Jukebox]:
    rows = await db.fetchall("SELECT * FROM jukebox.jukebox WHERE user = ?", (user,))
    for row in rows:

        if row.sp_playlists == None:
            print("cunt")
            await delete_jukebox(row.id)
    rows = await db.fetchall("SELECT * FROM jukebox.jukebox WHERE user = ?", (user,))

    return [Jukebox(**row) for row in rows]


async def delete_jukebox(juke_id: str):
    await db.execute(
        """
        DELETE FROM jukebox.jukebox WHERE id = ?
        """,
        (juke_id),
    )


#####################################PAYMENTS


async def create_jukebox_payment(
    song_id: str, payment_hash: str, juke_id: str
) -> JukeboxPayment:
    result = await db.execute(
        """
        INSERT INTO jukebox.jukebox_payment (payment_hash, juke_id, song_id, paid)
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
        f"UPDATE jukebox.jukebox_payment SET {q} WHERE payment_hash = ?",
        (*kwargs.values(), payment_hash),
    )
    return await get_jukebox_payment(payment_hash)


async def get_jukebox_payment(payment_hash: str) -> Optional[JukeboxPayment]:
    row = await db.fetchone(
        "SELECT * FROM jukebox.jukebox_payment WHERE payment_hash = ?", (payment_hash,)
    )
    return JukeboxPayment(**row) if row else None
