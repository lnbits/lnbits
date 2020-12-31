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
    duration: int,
    record_type: str
) -> Subdomains:
    await db.execute(
        """
        INSERT INTO subdomain (id, domain, email, subdomain, ip, wallet, sats, duration, paid, record_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (payment_hash, domain, email, subdomain, ip, wallet, sats, duration, False, record_type),
    )

    subdomain = await get_subdomain(payment_hash)
    assert subdomain, "Newly created subdomain couldn't be retrieved"
    return subdomain


async def set_subdomain_paid(payment_hash: str) -> Subdomains:
    row = await db.fetchone("SELECT s.*, d.domain as domain_name FROM subdomain s INNER JOIN domain d ON (s.domain = d.id) WHERE s.id = ?", (payment_hash,))
    if row[8] == False:
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

        amount = domaindata.amountmade + row[8]
        await db.execute(
            """
            UPDATE domain
            SET amountmade = ?
            WHERE id = ?
            """,
            (amount, row[1]),
        )

        subdomain = await get_subdomain(payment_hash)

        ### SEND REQUEST TO CLOUDFLARE
        url="https://api.cloudflare.com/client/v4/zones/" + domaindata.cf_zone_id + "/dns_records"
        header= {'Authorization': 'Bearer ' + domaindata.cf_token, 'Content-Type': 'application/json'}
        aRecord=subdomain.subdomain + '.' + subdomain.domain_name
        cf_response = ""
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    url,
                    headers=header,
                    json={
                        "type": subdomain.record_type,
                        "name": aRecord,
                        "content": subdomain.ip,
                        "ttl": 0,
                        "proxed": False
                    },
                    timeout=40,
                )
                cf_response = r.text
            except AssertionError:
                cf_response = "Error occured"

        ### Use webhook to notify about cloudflare registration
        if domaindata.webhook:
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.post(
                        domaindata.webhook,
                        json={
                            "domain": subdomain.domain_name,
                            "subdomain": subdomain.subdomain,
                            "record_type": subdomain.record_type,
                            "email": subdomain.email,
                            "ip": subdomain.ip,
                            "cost:": str(subdomain.sats) + " sats",
                            "duration": str(subdomain.duration) + " days",
                            "cf_response": cf_response
                        },
                        timeout=40,
                    )
                except AssertionError:
                    webhook = None

    subdomain = await get_subdomain(payment_hash)
    return


async def get_subdomain(subdomain_id: str) -> Optional[Subdomains]:
    row = await db.fetchone("SELECT s.*, d.domain as domain_name FROM subdomain s INNER JOIN domain d ON (s.domain = d.id) WHERE s.id = ?", (subdomain_id,))
    print(row)
    return Subdomains(**row) if row else None


async def get_subdomains(wallet_ids: Union[str, List[str]]) -> List[Subdomains]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(f"SELECT s.*, d.domain as domain_name FROM subdomain s INNER JOIN domain d ON (s.domain = d.id) WHERE s.wallet IN ({q})", (*wallet_ids,))

    return [Subdomains(**row) for row in rows]


async def delete_subdomain(subdomain_id: str) -> None:
    await db.execute("DELETE FROM subdomain WHERE id = ?", (subdomain_id,))


# Domains


async def create_domain(*, wallet: str, domain: str, cf_token: str, cf_zone_id: str, webhook: Optional[str] = None, description: str, cost: int, allowed_record_types: str) -> Domains:
    domain_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO domain (id, wallet, domain, webhook, cf_token, cf_zone_id, description, cost, amountmade, allowed_record_types)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (domain_id, wallet, domain, webhook, cf_token, cf_zone_id, description, cost, 0, allowed_record_types),
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



