from typing import List, Optional, Union

from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash

from .models import Paywall


def create_paywall(*, wallet_id: str, url: str, memo: str, amount: int) -> Paywall:
    with open_ext_db("paywall") as db:
        paywall_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO paywalls (id, wallet, secret, url, memo, amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (paywall_id, wallet_id, urlsafe_short_hash(), url, memo, amount),
        )

    return get_paywall(paywall_id)


def get_paywall(paywall_id: str) -> Optional[Paywall]:
    with open_ext_db("paywall") as db:
        row = db.fetchone("SELECT * FROM paywalls WHERE id = ?", (paywall_id,))

    return Paywall(**row) if row else None


def get_paywalls(wallet_ids: Union[str, List[str]]) -> List[Paywall]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("paywall") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM paywalls WHERE wallet IN ({q})", (*wallet_ids,))

    return [Paywall(**row) for row in rows]


def delete_paywall(paywall_id: str) -> None:
    with open_ext_db("paywall") as db:
        db.execute("DELETE FROM paywalls WHERE id = ?", (paywall_id,))
