from datetime import datetime, timedelta
from typing import List, Optional, Union

from loguru import logger

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Addresses, CreateAddress, CreateDomain, Domains


async def create_domain(data: CreateDomain) -> Domains:
    domain_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnaddress.domain (id, wallet, domain, webhook, cf_token, cf_zone_id, cost)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            domain_id,
            data.wallet,
            data.domain,
            data.webhook,
            data.cf_token,
            data.cf_zone_id,
            data.cost,
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
    row = await db.fetchone("SELECT * FROM lnaddress.domain WHERE id = ?", (domain_id,))
    assert row, "Newly updated domain couldn't be retrieved"
    return Domains(**row)


async def delete_domain(domain_id: str) -> None:

    await db.execute("DELETE FROM lnaddress.domain WHERE id = ?", (domain_id,))


async def get_domain(domain_id: str) -> Optional[Domains]:
    row = await db.fetchone("SELECT * FROM lnaddress.domain WHERE id = ?", (domain_id,))
    return Domains(**row) if row else None


async def get_domains(wallet_ids: Union[str, List[str]]) -> List[Domains]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM lnaddress.domain WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Domains(**row) for row in rows]


## ADRESSES


async def create_address(
    payment_hash: str, wallet: str, data: CreateAddress
) -> Addresses:
    await db.execute(
        """
        INSERT INTO lnaddress.address (id, wallet, domain, email, username, wallet_key, wallet_endpoint, sats, duration, paid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment_hash,
            wallet,
            data.domain,
            data.email,
            data.username,
            data.wallet_key,
            data.wallet_endpoint,
            data.sats,
            data.duration,
            False,
        ),
    )

    new_address = await get_address(payment_hash)
    assert new_address, "Newly created address couldn't be retrieved"
    return new_address


async def get_address(address_id: str) -> Optional[Addresses]:
    row = await db.fetchone(
        "SELECT a.* FROM lnaddress.address AS a INNER JOIN lnaddress.domain AS d ON a.id = ? AND a.domain = d.id",
        (address_id,),
    )
    return Addresses(**row) if row else None


async def get_address_by_username(username: str, domain: str) -> Optional[Addresses]:
    row = await db.fetchone(
        "SELECT a.* FROM lnaddress.address AS a INNER JOIN lnaddress.domain AS d ON a.username = ? AND d.domain = ?",
        (username, domain),
    )

    return Addresses(**row) if row else None


async def delete_address(address_id: str) -> None:
    await db.execute("DELETE FROM lnaddress.address WHERE id = ?", (address_id,))


async def get_addresses(wallet_ids: Union[str, List[str]]) -> List[Addresses]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM lnaddress.address WHERE wallet IN ({q})", (*wallet_ids,)
    )
    return [Addresses(**row) for row in rows]


async def set_address_paid(payment_hash: str) -> Addresses:
    address = await get_address(payment_hash)
    assert address

    if address.paid is False:
        await db.execute(
            """
            UPDATE lnaddress.address
            SET paid = true
            WHERE id = ?
            """,
            (payment_hash,),
        )

    new_address = await get_address(payment_hash)
    assert new_address, "Newly paid address couldn't be retrieved"
    return new_address


async def set_address_renewed(address_id: str, duration: int):
    address = await get_address(address_id)
    assert address

    extend_duration = int(address.duration) + duration
    await db.execute(
        """
        UPDATE lnaddress.address
        SET duration = ?
        WHERE id = ?
        """,
        (extend_duration, address_id),
    )
    updated_address = await get_address(address_id)
    assert updated_address, "Renewed address couldn't be retrieved"
    return updated_address


async def check_address_available(username: str, domain: str):
    (row,) = await db.fetchone(
        "SELECT COUNT(username) FROM lnaddress.address WHERE username = ? AND domain = ?",
        (username, domain),
    )
    return row


async def purge_addresses(domain_id: str):

    rows = await db.fetchall(
        "SELECT * FROM lnaddress.address WHERE domain = ?", (domain_id,)
    )

    now = datetime.now().timestamp()

    for row in rows:
        r = Addresses(**row).dict()

        start = datetime.fromtimestamp(r["time"])
        paid = r["paid"]
        pay_expire = now > start.timestamp() + 86400  # if payment wasn't made in 1 day
        expired = (
            now > (start + timedelta(days=r["duration"] + 1)).timestamp()
        )  # give user 1 day to topup is address

        if not paid and pay_expire:
            logger.debug("DELETE UNP_PAY_EXP", r["username"])
            await delete_address(r["id"])

        if paid and expired:
            logger.debug("DELETE PAID_EXP", r["username"])
            await delete_address(r["id"])
