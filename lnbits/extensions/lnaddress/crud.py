from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Domains

async def create_domain(
    *,
    wallet: str,
    domain: str,
    cf_token: str,
    cf_zone_id: str,
    webhook: Optional[str] = None,
    cost: int,
) -> Domains:
    domain_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnaddress.domain (id, wallet, domain, webhook, cf_token, cf_zone_id, cost)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            domain_id,
            wallet,
            domain,
            webhook,
            cf_token,
            cf_zone_id,
            cost,
        ),
    )

    new_domain = await get_domain(domain_id)
    assert new_domain, "Newly created domain couldn't be retrieved"
    return new_domain


async def update_domain(domain_id: str, **kwargs) -> Domains:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnaddress.domain SET {q} WHERE id = ?", (*kwargs.values(), domain_id)
    )
    row = await db.fetchone(
        "SELECT * FROM lnaddress.domain WHERE id = ?", (domain_id,)
    )
    assert row, "Newly updated domain couldn't be retrieved"
    return Domains(**row)

async def delete_domain(domain_id: str) -> None:
    await db.execute("DELETE FROM lnaddress.domain WHERE id = ?", (domain_id,))

async def get_domain(domain_id: str) -> Optional[Domains]:
    row = await db.fetchone(
        "SELECT * FROM lnaddress.domain WHERE id = ?", (domain_id,)
    )
    return Domains(**row) if row else None

async def get_domains(wallet_ids: Union[str, List[str]]) -> List[Domains]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM lnaddress.domain WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Domains(**row) for row in rows]
