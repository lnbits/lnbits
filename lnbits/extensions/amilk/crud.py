from base64 import urlsafe_b64encode
from uuid import uuid4
from typing import List, Optional, Union

from . import db
from .models import AMilk


async def create_amilk(*, wallet_id: str, lnurl: str, atime: int, amount: int) -> AMilk:
    amilk_id = urlsafe_b64encode(uuid4().bytes_le).decode("utf-8")
    await db.execute(
        """
        INSERT INTO amilks (id, wallet, lnurl, atime, amount)
        VALUES (?, ?, ?, ?, ?)
        """,
        (amilk_id, wallet_id, lnurl, atime, amount),
    )

    amilk = await get_amilk(amilk_id)
    assert amilk, "Newly created amilk_id couldn't be retrieved"
    return amilk


async def get_amilk(amilk_id: str) -> Optional[AMilk]:
    row = await db.fetchone("SELECT * FROM amilks WHERE id = ?", (amilk_id,))
    return AMilk(**row) if row else None


async def get_amilks(wallet_ids: Union[str, List[str]]) -> List[AMilk]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM amilks WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [AMilk(**row) for row in rows]


async def delete_amilk(amilk_id: str) -> None:
    await db.execute("DELETE FROM amilks WHERE id = ?", (amilk_id,))
