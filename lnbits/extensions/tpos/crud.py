from typing import List, Optional, Union

from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash

from .models import TPoS


def create_tpos(*, wallet_id: str, name: str, currency: str) -> TPoS:
    with open_ext_db("tpos") as db:
        tpos_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO tposs (id, wallet, name, currency)
            VALUES (?, ?, ?, ?)
            """,
            (tpos_id, wallet_id, name, currency),
        )

    return get_tpos(tpos_id)


def get_tpos(tpos_id: str) -> Optional[TPoS]:
    with open_ext_db("tpos") as db:
        row = db.fetchone("SELECT * FROM tposs WHERE id = ?", (tpos_id,))

    return TPoS.from_row(row) if row else None


def get_tposs(wallet_ids: Union[str, List[str]]) -> List[TPoS]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("tpos") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM tposs WHERE wallet IN ({q})", (*wallet_ids,))

    return [TPoS.from_row(row) for row in rows]


def delete_tpos(tpos_id: str) -> None:
    with open_ext_db("tpos") as db:
        db.execute("DELETE FROM tposs WHERE id = ?", (tpos_id,))
