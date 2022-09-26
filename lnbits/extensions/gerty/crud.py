from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Gerty


async def create_gerty(wallet_id: str, data: Gerty) -> Gerty:
    gerty_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO gerty.gertys (id, name, wallet, lnbits_wallets, sats_quote, exchange, onchain_stats, ln_stats)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gerty_id,
            data.name,
            data.wallet,
            data.lnbits_wallets,
            data.sats_quote,
            data.exchange,
            data.onchain_sats,
            data.ln_stats,
        ),
    )

    gerty = await get_gerty(gerty_id)
    assert gerty, "Newly created gerty couldn't be retrieved"
    return gerty
    

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
