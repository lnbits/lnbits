from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash
import time

from . import db
from .models import (
    Gerty, 
    Mempool, 
    Fees_recommended, 
    Hashrate_1w, 
    Hashrate_1m,
    Statistics,
    Difficulty_adjustment,
    Tip_height)

async def create_gerty(wallet_id: str, data: Gerty) -> Gerty:
    gerty_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO gerty.gertys (
        id,
        name,
        wallet,
        utc_offset,
        type,
        lnbits_wallets,
        mempool_endpoint,
        exchange,
        display_preferences,
        refresh_time
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gerty_id,
            data.name,
            data.wallet,
            data.utc_offset,
            data.type,
            data.lnbits_wallets,
            data.mempool_endpoint,
            data.exchange,
            data.display_preferences,
            data.refresh_time,
        ),
    )

    gerty = await get_gerty(gerty_id)
    assert gerty, "Newly created gerty couldn't be retrieved"
    return gerty


async def update_gerty(gerty_id: str, **kwargs) -> Gerty:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE gerty.gertys SET {q} WHERE id = ?", (*kwargs.values(), gerty_id)
    )
    return await get_gerty(gerty_id)


async def get_gerty(gerty_id: str) -> Optional[Gerty]:
    row = await db.fetchone("SELECT * FROM gerty.gertys WHERE id = ?", (gerty_id,))
    return Gerty(**row) if row else None


async def get_gertys(wallet_ids: Union[str, List[str]]) -> List[Gerty]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM gerty.gertys WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Gerty(**row) for row in rows]


async def delete_gerty(gerty_id: str) -> None:
    await db.execute("DELETE FROM gerty.gertys WHERE id = ?", (gerty_id,))


#############MEMPOOL###########

async def get_fees_recommended(gerty) -> Optional[Fees_recommended]:
    row = await db.fetchone("SELECT * FROM gerty.fees_recommended", ())
    if int(time.time()) - row.time > 20:
        async with httpx.AsyncClient() as client:
            response = await client.get(gerty.mempool_endpoint + "/api/v1/fees/recommended")
            if response.status_code == 200:
                await db.execute(
                    """
                    UPDATE gerty.fees_recommended
                    SET data = ?, time = ?
                    """,
                    (response.json(), int(time.time())),
                )
            return Fees_recommended(**response) if response else None
    else:
        return Fees_recommended(**row) if row else None

async def get_hashrate_1w(gerty) -> Optional[Hashrate_1w]:
    row = await db.fetchone("SELECT * FROM gerty.hashrate_1w", ())
    if int(time.time()) - row.time > 20:
        async with httpx.AsyncClient() as client:
            response = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/1w")
            if response.status_code == 200:
                await db.execute(
                    """
                    UPDATE gerty.hashrate_1w
                    SET data = ?, time = ?
                    """,
                    (response.json(), int(time.time())),
                )
            return Hashrate_1w(**response) if response else None
    else:
        return Hashrate_1w(**row) if row else None

async def get_hashrate_1m(gerty) -> Optional[Hashrate_1m]:
    row = await db.fetchone("SELECT * FROM gerty.hashrate_1m", ())
    if int(time.time()) - row.time > 20:
        async with httpx.AsyncClient() as client:
            response = await client.get(gerty.mempool_endpoint + "/api/v1/mining/hashrate/1m")
            if response.status_code == 200:
                await db.execute(
                    """
                    UPDATE gerty.hashrate_1m
                    SET data = ?, time = ?
                    """,
                    (response.json(), int(time.time())),
                )
            return Hashrate_1m(**response) if response else None
    else:
        return Hashrate_1m(**row) if row else None

async def get_statistics(gerty) -> Optional[Statistics]:
    row = await db.fetchone("SELECT * FROM gerty.statistics", ())
    if int(time.time()) - row.time > 20:
        async with httpx.AsyncClient() as client:
            response = await client.get(gerty.mempool_endpoint + "/api/v1/lightning/statistics/latest")
            if response.status_code == 200:
                await db.execute(
                    """
                    UPDATE gerty.statistics
                    SET data = ?, time = ?
                    """,
                    (response.json(), int(time.time())),
                )
            return Statistics(**response) if response else None
    else:
        return Statistics(**row) if row else None

async def get_difficulty_adjustment(gerty) -> Optional[Difficulty_adjustment]:
    row = await db.fetchone("SELECT * FROM gerty.difficulty_adjustment", ())
    logger.debug(int(time.time()))
    logger.debug(row.time)
    logger.debug(int(time.time()) - row.time)
    if int(time.time()) - row.time > 20:
        async with httpx.AsyncClient() as client:
            response = await client.get(gerty.mempool_endpoint + "/api/v1/difficulty-adjustment")
            if response.status_code == 200:
                await db.execute(
                    """
                    UPDATE gerty.difficulty_adjustment
                    SET data = ?, time = ?
                    """,
                    (response.json(), int(time.time())),
                )
            return Difficulty_adjustment(**response) if response else None
    else:
        return Difficulty_adjustment(**row) if row else None

async def get_tip_height() -> Optional[Tip_height]:
    row = await db.fetchone("SELECT * FROM gerty.tip_height", ())
    if int(time.time()) - row.time > 20:
        async with httpx.AsyncClient() as client:
            response = await client.get(gerty.mempool_endpoint + "/api/blocks/tip/height")
            if response.status_code == 200:
                await db.execute(
                    """
                    UPDATE gerty.tip_height
                    SET data = ?, time = ?
                    """,
                    (response.json(), int(time.time())),
                )
            return Tip_height(**response) if response else None
    else:
        return Tip_height(**row) if row else None

async def get_mempool() -> Optional[Mempool]:
    row = await db.fetchone("SELECT * FROM gerty.mempool", ())
    if int(time.time()) - row.time > 20:
        async with httpx.AsyncClient() as client:
            response = await client.get(gerty.mempool_endpoint + "/api/mempool")
            if response.status_code == 200:
                await db.execute(
                    """
                    UPDATE gerty.mempool
                    SET data = ?, time = ?
                    """,
                    (response.json(), int(time.time())),
                )
            return Mempool(**response) if response else None
    else:
        return Mempool(**row) if row else None