from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Address, CreateAddressData, CreateDomainData, EditDomainData, Domain


async def get_domain(domain_id: str) -> Optional[Domain]:
    row = await db.fetchone(
        "SELECT * FROM nostrnip5.domains WHERE id = ?", (domain_id,)
    )
    return Domain.from_row(row) if row else None


async def get_domain_by_name(domain: str) -> Optional[Domain]:
    row = await db.fetchone(
        "SELECT * FROM nostrnip5.domains WHERE domain = ?", (domain,)
    )
    return Domain.from_row(row) if row else None


async def get_domains(wallet_ids: Union[str, List[str]]) -> List[Domain]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM nostrnip5.domains WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Domain.from_row(row) for row in rows]


async def get_address(domain_id: str, address_id: str) -> Optional[Address]:
    row = await db.fetchone(
        "SELECT * FROM nostrnip5.addresses WHERE domain_id = ? AND id = ?",
        (
            domain_id,
            address_id,
        ),
    )
    return Address.from_row(row) if row else None


async def get_address_by_local_part(
    domain_id: str, local_part: str
) -> Optional[Address]:
    row = await db.fetchone(
        "SELECT * FROM nostrnip5.addresses WHERE domain_id = ? AND local_part = ?",
        (
            domain_id,
            local_part.lower(),
        ),
    )
    return Address.from_row(row) if row else None


async def get_addresses(domain_id: str) -> List[Address]:
    rows = await db.fetchall(
        f"SELECT * FROM nostrnip5.addresses WHERE domain_id = ?", (domain_id,)
    )

    return [Address.from_row(row) for row in rows]


async def get_all_addresses(wallet_ids: Union[str, List[str]]) -> List[Address]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT a.*
        FROM nostrnip5.addresses a
        JOIN nostrnip5.domains d ON d.id = a.domain_id
        WHERE d.wallet IN ({q})
        """,
        (*wallet_ids,),
    )

    return [Address.from_row(row) for row in rows]


async def activate_address(domain_id: str, address_id: str) -> Address:
    await db.execute(
        """
        UPDATE nostrnip5.addresses
        SET active = true
        WHERE domain_id = ?
        AND id = ?
        """,
        (
            domain_id,
            address_id,
        ),
    )

    address = await get_address(domain_id, address_id)
    assert address, "Newly updated address couldn't be retrieved"
    return address


async def rotate_address(domain_id: str, address_id: str, pubkey: str) -> Address:
    await db.execute(
        """
        UPDATE nostrnip5.addresses
        SET pubkey = ?
        WHERE domain_id = ?
        AND id = ?
        """,
        (
            pubkey,
            domain_id,
            address_id,
        ),
    )

    address = await get_address(domain_id, address_id)
    assert address, "Newly updated address couldn't be retrieved"
    return address


async def delete_domain(domain_id) -> bool:
    await db.execute(
        """
        DELETE FROM nostrnip5.addresses WHERE domain_id = ?
        """,
        (domain_id,),
    )

    await db.execute(
        """
        DELETE FROM nostrnip5.domains WHERE id = ?
        """,
        (domain_id,),
    )

    return True


async def delete_address(address_id):
    await db.execute(
        """
        DELETE FROM nostrnip5.addresses WHERE id = ?
        """,
        (address_id,),
    )


async def create_address_internal(domain_id: str, data: CreateAddressData) -> Address:
    address_id = urlsafe_short_hash()

    await db.execute(
        """
        INSERT INTO nostrnip5.addresses (id, domain_id, local_part, pubkey, active)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            address_id,
            domain_id,
            data.local_part.lower(),
            data.pubkey,
            False,
        ),
    )

    address = await get_address(domain_id, address_id)
    assert address, "Newly created address couldn't be retrieved"
    return address

async def update_domain_internal(wallet_id: str, data: EditDomainData) -> Domain:
    if data.currency != "Satoshis":
        amount = data.amount * 100
    else:
        amount = data.amount
    print(data)
    await db.execute(
        """
        UPDATE nostrnip5.domains
        SET amount = ?, currency = ?
        WHERE id = ?
        """,
        (int(amount), data.currency, data.id),
    )

    domain = await get_domain(data.id)
    assert domain, "Domain couldn't be updated"
    return domain

async def create_domain_internal(wallet_id: str, data: CreateDomainData) -> Domain:
    domain_id = urlsafe_short_hash()

    if data.currency != "Satoshis":
        amount = data.amount * 100
    else:
        amount = data.amount

    await db.execute(
        """
        INSERT INTO nostrnip5.domains (id, wallet, currency, amount, domain)
        VALUES (?, ?, ?, ?, ?)
        """,
        (domain_id, wallet_id, data.currency, int(amount), data.domain),
    )

    domain = await get_domain(domain_id)
    assert domain, "Newly created domain couldn't be retrieved"
    return domain
