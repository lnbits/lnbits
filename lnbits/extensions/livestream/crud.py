from typing import List, Optional

from lnbits.core.crud import create_account, create_wallet
from lnbits.db import SQLITE

from . import db
from .models import Livestream, Producer, Track


async def create_livestream(*, wallet_id: str) -> int:
    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await (method)(
        f"""
        INSERT INTO livestream.livestreams (wallet)
        VALUES (?)
        {returning}
        """,
        (wallet_id,),
    )

    if db.type == SQLITE:
        return result._result_proxy.lastrowid
    else:
        return result[0]  # type: ignore


async def get_livestream(ls_id: int) -> Optional[Livestream]:
    row = await db.fetchone(
        "SELECT * FROM livestream.livestreams WHERE id = ?", (ls_id,)
    )
    return Livestream(**row) if row else None


async def get_livestream_by_track(track_id: int) -> Optional[Livestream]:
    row = await db.fetchone(
        """
        SELECT * FROM livestream.tracks WHERE tracks.id = ?
        """,
        (track_id,),
    )
    row2 = await db.fetchone(
        """
        SELECT * FROM livestream.livestreams WHERE livestreams.id = ?
        """,
        (row.livestream,),
    )
    return Livestream(**row2) if row2 else None


async def get_or_create_livestream_by_wallet(wallet: str) -> Optional[Livestream]:
    row = await db.fetchone(
        "SELECT * FROM livestream.livestreams WHERE wallet = ?", (wallet,)
    )

    if not row:
        # create on the fly
        ls_id = await create_livestream(wallet_id=wallet)
        return await get_livestream(ls_id)

    return Livestream(**row) if row else None


async def update_current_track(ls_id: int, track_id: Optional[int]):
    await db.execute(
        "UPDATE livestream.livestreams SET current_track = ? WHERE id = ?",
        (track_id, ls_id),
    )


async def update_livestream_fee(ls_id: int, fee_pct: int):
    await db.execute(
        "UPDATE livestream.livestreams SET fee_pct = ? WHERE id = ?", (fee_pct, ls_id)
    )


async def add_track(
    livestream: int,
    name: str,
    download_url: Optional[str],
    price_msat: int,
    producer: Optional[int],
) -> int:
    result = await db.execute(
        """
        INSERT INTO livestream.tracks (livestream, name, download_url, price_msat, producer)
        VALUES (?, ?, ?, ?, ?)
        """,
        (livestream, name, download_url, price_msat, producer),
    )
    return result._result_proxy.lastrowid


async def update_track(
    livestream: int,
    track_id: int,
    name: str,
    download_url: Optional[str],
    price_msat: int,
    producer: int,
) -> int:
    result = await db.execute(
        """
        UPDATE livestream.tracks SET
          name = ?,
          download_url = ?,
          price_msat = ?,
          producer = ?
        WHERE livestream = ? AND id = ?
        """,
        (name, download_url, price_msat, producer, livestream, track_id),
    )
    return result._result_proxy.lastrowid


async def get_track(track_id: Optional[int]) -> Optional[Track]:
    if not track_id:
        return None

    row = await db.fetchone(
        """
        SELECT id, download_url, price_msat, name, producer
        FROM livestream.tracks WHERE id = ?
        """,
        (track_id,),
    )
    return Track(**row) if row else None


async def get_tracks(livestream: int) -> List[Track]:
    rows = await db.fetchall(
        """
        SELECT id, download_url, price_msat, name, producer
        FROM livestream.tracks WHERE livestream = ?
        """,
        (livestream,),
    )
    return [Track(**row) for row in rows]


async def delete_track_from_livestream(livestream: int, track_id: int):
    await db.execute(
        """
        DELETE FROM livestream.tracks WHERE livestream = ? AND id = ?
        """,
        (livestream, track_id),
    )


async def add_producer(livestream: int, name: str) -> int:
    name = name.strip()

    existing = await db.fetchall(
        """
        SELECT id FROM livestream.producers
        WHERE livestream = ? AND lower(name) = ?
        """,
        (livestream, name.lower()),
    )
    if existing:
        return existing[0].id

    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="livestream: " + name)

    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await method(
        f"""
        INSERT INTO livestream.producers (livestream, name, "user", wallet)
        VALUES (?, ?, ?, ?)
        {returning}
        """,
        (livestream, name, user.id, wallet.id),
    )
    if db.type == SQLITE:
        return result._result_proxy.lastrowid
    else:
        return result[0]  # type: ignore


async def get_producer(producer_id: int) -> Optional[Producer]:
    row = await db.fetchone(
        """
        SELECT id, "user", wallet, name
        FROM livestream.producers WHERE id = ?
        """,
        (producer_id,),
    )
    return Producer(**row) if row else None


async def get_producers(livestream: int) -> List[Producer]:
    rows = await db.fetchall(
        """
        SELECT id, "user", wallet, name
        FROM livestream.producers WHERE livestream = ?
        """,
        (livestream,),
    )
    return [Producer(**row) for row in rows]
