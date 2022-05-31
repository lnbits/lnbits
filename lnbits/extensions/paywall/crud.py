from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Paywall


async def create_paywall(
    *,
    wallet_id: str,
    url: str,
    memo: str,
    description: Optional[str] = None,
    amount: int = 0,
    remembers: bool = True,
) -> Paywall:
    paywall_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO paywall.paywalls (id, wallet, url, memo, description, amount, remembers)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (paywall_id, wallet_id, url, memo, description, amount, int(remembers)),
    )

    paywall = await get_paywall(paywall_id)
    assert paywall, "Newly created paywall couldn't be retrieved"
    return paywall


async def get_paywall(paywall_id: str) -> Optional[Paywall]:
    row = await db.fetchone(
        "SELECT * FROM paywall.paywalls WHERE id = ?", (paywall_id,)
    )

    return Paywall.from_row(row) if row else None


async def get_paywalls(wallet_ids: Union[str, List[str]]) -> List[Paywall]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM paywall.paywalls WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Paywall.from_row(row) for row in rows]


async def delete_paywall(paywall_id: str) -> None:
    await db.execute("DELETE FROM paywall.paywalls WHERE id = ?", (paywall_id,))
