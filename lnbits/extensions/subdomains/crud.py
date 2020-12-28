from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Domains, Subdomains
import httpx

from lnbits.extensions import subdomains

async def create_subdomain(
    payment_hash: str,
    wallet: str,
    domain: str,
    subdomain: str,
    email: str,
    ip: str,
    sats: int,
) -> Subdomains:
    await db.execute(
        """
        INSERT INTO subdomain (id, domain, email, subdomain, ip, wallet, sats, paid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (payment_hash, domain, email, subdomain, ip, wallet, sats, False),
    )

    subdomain = await get_subdomain(payment_hash)
    assert subdomain, "Newly created subdomain couldn't be retrieved"
    return subdomain


async def set_subdomain_paid(payment_hash: str) -> Subdomains:
    row = await db.fetchone("SELECT * FROM subdomain WHERE id = ?", (payment_hash,))
    if row[7] == False:
        await db.execute(
            """
            UPDATE subdomain
            SET paid = true
            WHERE id = ?
            """,
            (payment_hash,),
        )

        domaindata = await get_domain(row[1])
        assert domaindata, "Couldn't get domain from paid subdomain"

        amount = domaindata.amountmade + row[7]
        await db.execute(
            """
            UPDATE domain
            SET amountmade = ?
            WHERE id = ?
            """,
            (amount, row[1]),
        )
        
        subdomain = await get_subdomain(payment_hash)
        if domaindata.webhook:
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.post(
                        domaindata.webhook,
                        json={
                            "domain": subdomain.domain,
                            "subdomain": subdomain.subdomain,
                            "email": subdomain.email,
                            "ip": subdomain.ip
                        },
                        timeout=40,
                    )
                except AssertionError:
                    webhook = None
            return subdomain
    subdomain = await get_subdomain(payment_hash)
    return


async def get_subdomain(subdomain_id: str) -> Optional[Subdomains]:
    row = await db.fetchone("SELECT * FROM subdomain WHERE id = ?", (subdomain_id,))
    return Subdomains(**row) if row else None


async def get_subdomains(wallet_ids: Union[str, List[str]]) -> List[Subdomains]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(f"SELECT * FROM subdomain WHERE wallet IN ({q})", (*wallet_ids,))

    return [Subdomains(**row) for row in rows]


async def delete_subdomain(subdomain_id: str) -> None:
    await db.execute("DELETE FROM subdomain WHERE id = ?", (subdomain_id,))


# Domains


async def create_domain(*, wallet: str, domain: str, cfToken: str, cfZoneId: str, webhook: Optional[str] = None, description: str, cost: int) -> Domains:
    domain_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO domain (id, wallet, domain, webhook, cf_token, cf_zone_id, description, cost, amountmade)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (domain_id, wallet, domain, webhook, cfToken, cfZoneId, description, cost, 0),
    )

    domain = await get_domain(domain_id)
    assert domain, "Newly created domain couldn't be retrieved"
    return domain


async def update_domain(domain_id: str, **kwargs) -> Domains:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(f"UPDATE domain SET {q} WHERE id = ?", (*kwargs.values(), domain_id))
    row = await db.fetchone("SELECT * FROM domain WHERE id = ?", (domain_id,))
    assert row, "Newly updated domain couldn't be retrieved"
    return Domains(**row)


async def get_domain(domain_id: str) -> Optional[Domains]:
    row = await db.fetchone("SELECT * FROM domain WHERE id = ?", (domain_id,))
    return Domains(**row) if row else None


async def get_domains(wallet_ids: Union[str, List[str]]) -> List[Domains]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(f"SELECT * FROM domain WHERE wallet IN ({q})", (*wallet_ids,))

    return [Domains(**row) for row in rows]


async def delete_domain(domain_id: str) -> None:
    await db.execute("DELETE FROM domain WHERE id = ?", (domain_id,))
