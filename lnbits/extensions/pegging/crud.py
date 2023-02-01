from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreatePeggingData, Pegging


async def create_pegging(wallet_id: str, data: CreatePeggingData) -> Pegging:
    row = await db.fetchone("SELECT * FROM pegging.pegs WHERE wallet = ?", (wallet_id,))
    assert not row, "Register only one hedge per wallet"

    peg_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO pegging.pegs (id, name, wallet, percent, currency, base_url, api_key, api_secret, api_passphrase)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            peg_id,
            data.name,
            wallet_id,
            data.percent,
            data.currency,
            data.base_url,
            data.api_key,
            data.api_secret,
            data.api_passphrase,
        ),
    )

    pegging = await get_pegging(peg_id)
    assert pegging, "Newly created pegging couldn't be retrieved"
    return pegging


async def get_pegging(peg_id: Union[str, List[str]]) -> Optional[Pegging]:
    row = await db.fetchone("SELECT * FROM pegging.pegs WHERE id = ?", (peg_id,))
    return Pegging(**row) if row else None


async def get_pegged_currencies(currency: str) -> List[Pegging]:
    rows = await db.fetchall(
        "SELECT * FROM pegging.pegs WHERE currency = ?", (currency,)
    )
    return [Pegging(**row) for row in rows]


async def get_peggings(wallet_ids: Union[str, List[str]]) -> List[Pegging]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM pegging.pegs WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Pegging(**row) for row in rows]


async def delete_pegging(peg_id: str) -> None:
    await db.execute("DELETE FROM pegging.pegs WHERE id = ?", (peg_id,))
