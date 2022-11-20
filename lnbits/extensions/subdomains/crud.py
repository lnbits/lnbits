from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateDomain, CreateSubdomain, Domains, Subdomains


async def create_subdomain(payment_hash, wallet, data: CreateSubdomain) -> Subdomains:
    await db.execute(
        """
        INSERT INTO subdomains.subdomain (id, domain, email, subdomain, ip, wallet, sats, duration, paid, record_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment_hash,
            data.domain,
            data.email,
            data.subdomain,
            data.ip,
            wallet,
            data.sats,
            data.duration,
            False,
            data.record_type,
        ),
    )

    new_subdomain = await get_subdomain(payment_hash)
    assert new_subdomain, "Newly created subdomain couldn't be retrieved"
    return new_subdomain


async def set_subdomain_paid(payment_hash: str) -> Subdomains:
    row = await db.fetchone(
        "SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.id = ?",
        (payment_hash,),
    )
    if row[8] == False:
        await db.execute(
            """
            UPDATE subdomains.subdomain
            SET paid = true
            WHERE id = ?
            """,
            (payment_hash,),
        )

        domaindata = await get_domain(row[1])
        assert domaindata, "Couldn't get domain from paid subdomain"

        amount = domaindata.amountmade + row[8]
        await db.execute(
            """
            UPDATE subdomains.domain
            SET amountmade = ?
            WHERE id = ?
            """,
            (amount, row[1]),
        )

    new_subdomain = await get_subdomain(payment_hash)
    assert new_subdomain, "Newly paid subdomain couldn't be retrieved"
    return new_subdomain


async def get_subdomain(subdomain_id: str) -> Optional[Subdomains]:
    row = await db.fetchone(
        "SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.id = ?",
        (subdomain_id,),
    )
    return Subdomains(**row) if row else None


async def get_subdomainBySubdomain(subdomain: str) -> Optional[Subdomains]:
    row = await db.fetchone(
        "SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.subdomain = ?",
        (subdomain,),
    )
    return Subdomains(**row) if row else None


async def get_subdomains(wallet_ids: Union[str, List[str]]) -> List[Subdomains]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT s.*, d.domain as domain_name FROM subdomains.subdomain s INNER JOIN subdomains.domain d ON (s.domain = d.id) WHERE s.wallet IN ({q})",
        (*wallet_ids,),
    )

    return [Subdomains(**row) for row in rows]


async def delete_subdomain(subdomain_id: str) -> None:
    await db.execute("DELETE FROM subdomains.subdomain WHERE id = ?", (subdomain_id,))


# Domains


async def create_domain(data: CreateDomain) -> Domains:
    domain_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO subdomains.domain (id, wallet, domain, webhook, cf_token, cf_zone_id, description, cost, amountmade, allowed_record_types)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            domain_id,
            data.wallet,
            data.domain,
            data.webhook,
            data.cf_token,
            data.cf_zone_id,
            data.description,
            data.cost,
            0,
            data.allowed_record_types,
        ),
    )

    new_domain = await get_domain(domain_id)
    assert new_domain, "Newly created domain couldn't be retrieved"
    return new_domain


async def update_domain(domain_id: str, **kwargs) -> Domains:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE subdomains.domain SET {q} WHERE id = ?", (*kwargs.values(), domain_id)
    )
    row = await db.fetchone(
        "SELECT * FROM subdomains.domain WHERE id = ?", (domain_id,)
    )
    assert row, "Newly updated domain couldn't be retrieved"
    return Domains(**row)


async def get_domain(domain_id: str) -> Optional[Domains]:
    row = await db.fetchone(
        "SELECT * FROM subdomains.domain WHERE id = ?", (domain_id,)
    )
    return Domains(**row) if row else None


async def get_domains(wallet_ids: Union[str, List[str]]) -> List[Domains]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM subdomains.domain WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Domains(**row) for row in rows]


async def delete_domain(domain_id: str) -> None:
    await db.execute("DELETE FROM subdomains.domain WHERE id = ?", (domain_id,))
