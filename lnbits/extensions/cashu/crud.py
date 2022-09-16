from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Cashu, Pegs


async def create_cashu(wallet_id: str, data: Cashu) -> Cashu:
    cashu_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO cashu.cashu (id, wallet, name, tickershort, fraction, maxsats, coins)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cashu_id,
            wallet_id,
            data.name,
            data.tickershort,
            data.fraction,
            data.maxsats,
            data.coins
        ),
    )

    cashu = await get_cashu(cashu_id)
    assert cashu, "Newly created cashu couldn't be retrieved"
    return cashu


async def get_cashu(cashu_id: str) -> Optional[Cashu]:
    row = await db.fetchone("SELECT * FROM cashu.cashu WHERE id = ?", (cashu_id,))
    return Cashu(**row) if row else None


async def get_cashus(wallet_ids: Union[str, List[str]]) -> List[Cashu]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM cashu.cashu WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Cashu(**row) for row in rows]


async def delete_cashu(cashu_id: str) -> None:
    await db.execute("DELETE FROM cashu.cashu WHERE id = ?", (cashu_id,))
