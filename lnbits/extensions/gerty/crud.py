from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Gerty


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
