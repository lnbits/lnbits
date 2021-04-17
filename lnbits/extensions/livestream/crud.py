from typing import List, Optional

from lnbits.core.crud import create_account, create_wallet

from . import db
from .models import Livestream, Track, Producer


async def create_livestream(*, wallet_id: str) -> int:
    result = await db.execute(
        """
        INSERT INTO livestreams (wallet)
        VALUES (?)
        """,
        (wallet_id,),
    )
    return result._result_proxy.lastrowid


async def get_livestream(ls_id: int) -> Optional[Livestream]:
    row = await db.fetchone("SELECT * FROM livestreams WHERE id = ?", (ls_id,))
    return Livestream(**dict(row)) if row else None


async def get_livestream_by_track(track_id: int) -> Optional[Livestream]:
    row = await db.fetchone(
        """
        SELECT livestreams.* FROM livestreams
        INNER JOIN tracks ON tracks.livestream = livestreams.id
        WHERE tracks.id = ?
        """,
        (track_id,),
    )
    return Livestream(**dict(row)) if row else None


async def get_or_create_livestream_by_wallet(wallet: str) -> Optional[Livestream]:
    row = await db.fetchone("SELECT * FROM livestreams WHERE wallet = ?", (wallet,))

    if not row:
        # create on the fly
        ls_id = await create_livestream(wallet_id=wallet)
        return await get_livestream(ls_id)

    return Livestream(**dict(row)) if row else None


async def update_current_track(ls_id: int, track_id: Optional[int]):
    await db.execute(
        "UPDATE livestreams SET current_track = ? WHERE id = ?",
        (track_id, ls_id),
    )


async def update_livestream_fee(ls_id: int, fee_pct: int):
    await db.execute(
        "UPDATE livestreams SET fee_pct = ? WHERE id = ?",
        (fee_pct, ls_id),
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
        INSERT INTO tracks (livestream, name, download_url, price_msat, producer)
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
        UPDATE tracks SET
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
        FROM tracks WHERE id = ?
        """,
        (track_id,),
    )
    return Track(**dict(row)) if row else None


async def get_tracks(livestream: int) -> List[Track]:
    rows = await db.fetchall(
        """
        SELECT id, download_url, price_msat, name, producer
        FROM tracks WHERE livestream = ?
        """,
        (livestream,),
    )
    return [Track(**dict(row)) for row in rows]


async def delete_track_from_livestream(livestream: int, track_id: int):
    await db.execute(
        """
        DELETE FROM tracks WHERE livestream = ? AND id = ?
        """,
        (livestream, track_id),
    )


async def add_producer(livestream: int, name: str) -> int:
    name = name.strip()

    existing = await db.fetchall(
        """
        SELECT id FROM producers
        WHERE livestream = ? AND lower(name) = ?
        """,
        (livestream, name.lower()),
    )
    if existing:
        return existing[0].id

    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="livestream: " + name)

    result = await db.execute(
        """
        INSERT INTO producers (livestream, name, user, wallet)
        VALUES (?, ?, ?, ?)
        """,
        (livestream, name, user.id, wallet.id),
    )
    return result._result_proxy.lastrowid


async def get_producer(producer_id: int) -> Optional[Producer]:
    row = await db.fetchone(
        """
        SELECT id, user, wallet, name
        FROM producers WHERE id = ?
        """,
        (producer_id,),
    )
    return Producer(**dict(row)) if row else None


async def get_producers(livestream: int) -> List[Producer]:
    rows = await db.fetchall(
        """
        SELECT id, user, wallet, name
        FROM producers WHERE livestream = ?
        """,
        (livestream,),
    )
    return [Producer(**dict(row)) for row in rows]
