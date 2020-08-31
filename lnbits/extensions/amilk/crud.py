from base64 import urlsafe_b64encode
from uuid import uuid4
from typing import List, Optional, Union

from lnbits.db import open_ext_db

from .models import AMilk


def create_amilk(*, wallet_id: str, lnurl: str, atime: int, amount: int) -> AMilk:
    with open_ext_db("amilk") as db:
        amilk_id = urlsafe_b64encode(uuid4().bytes_le).decode("utf-8")
        db.execute(
            """
            INSERT INTO amilks (id, wallet, lnurl, atime, amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (amilk_id, wallet_id, lnurl, atime, amount),
        )

    return get_amilk(amilk_id)


def get_amilk(amilk_id: str) -> Optional[AMilk]:
    with open_ext_db("amilk") as db:
        row = db.fetchone("SELECT * FROM amilks WHERE id = ?", (amilk_id,))

    return AMilk(**row) if row else None


def get_amilks(wallet_ids: Union[str, List[str]]) -> List[AMilk]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("amilk") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM amilks WHERE wallet IN ({q})", (*wallet_ids,))

    return [AMilk(**row) for row in rows]


def delete_amilk(amilk_id: str) -> None:
    with open_ext_db("amilk") as db:
        db.execute("DELETE FROM amilks WHERE id = ?", (amilk_id,))
