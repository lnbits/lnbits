from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateTposData, TPoS


async def create_tpos(wallet_id: str, data: CreateTposData) -> TPoS:
    tpos_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO tpos.tposs (id, wallet, name, currency, tip_options, tip_wallet)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            tpos_id,
            wallet_id,
            data.name,
            data.currency,
            data.tip_options,
            data.tip_wallet,
        ),
    )

    tpos = await get_tpos(tpos_id)
    assert tpos, "Newly created tpos couldn't be retrieved"
    return tpos


async def get_tpos(tpos_id: str) -> Optional[TPoS]:
    row = await db.fetchone("SELECT * FROM tpos.tposs WHERE id = ?", (tpos_id,))
    return TPoS(**row) if row else None


async def get_tposs(wallet_ids: Union[str, List[str]]) -> List[TPoS]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM tpos.tposs WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [TPoS(**row) for row in rows]


async def delete_tpos(tpos_id: str) -> None:
    await db.execute("DELETE FROM tpos.tposs WHERE id = ?", (tpos_id,))
