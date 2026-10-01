from sqlalchemy import text  # type: ignore[import-untyped]

from lnbits.core.crud.wallets_onchain import get_onchain_wallet
from lnbits.core.db import db
from lnbits.core.models.onchain import Address
from lnbits.db import SQLITE, model_to_dict
from lnbits.helpers import urlsafe_short_hash
from lnbits.onchain.helpers import derive_address

ADDRESS_COLUMNS = ", ".join(Address.__fields__)
MASTERPUB_SQL = (
    "json_extract(onchain_meta, '$.masterpub')"
    if db.type == SQLITE
    else "CAST(onchain_meta AS JSONB)->>'masterpub'"
)


async def get_fresh_address(wallet_id: str) -> Address | None:
    # todo: move logic to views_api after satspay refactoring
    wallet = await get_onchain_wallet(wallet_id)

    if not wallet or not wallet.onchain_wallet_kind:
        return None

    # Atomically reserve an index across concurrent browsers/workers.
    async with db.connect() as conn:
        result = await conn.conn.execute(
            text(f"""
            UPDATE wallets SET onchain_address_no =
                CASE WHEN onchain_address_no < COALESCE((
                    SELECT MAX(address_index) FROM onchain_addresses
                    WHERE wallet = :wallet AND branch_index = 0 AND has_activity = true
                ), -1) THEN (
                    SELECT MAX(address_index) FROM onchain_addresses
                    WHERE wallet = :wallet AND branch_index = 0 AND has_activity = true
                ) + 1 ELSE onchain_address_no + 1 END
            WHERE id = :wallet AND wallet_type = 'onchain'
                AND onchain_wallet_kind IS NOT NULL
                AND {MASTERPUB_SQL} = :masterpub
            RETURNING onchain_address_no AS address_no
        """),  # noqa: S608
            {"wallet": wallet_id, "masterpub": wallet.onchain_meta.masterpub},
        )
        row = result.mappings().first()
        await conn.conn.commit()
    if not row:
        return None
    index = row["address_no"]
    address = await get_address_at_index(wallet_id, 0, index)
    if not address:
        await create_fresh_addresses(wallet_id, index, index + 1)
        address = await get_address_at_index(wallet_id, 0, index)

    return address


async def create_fresh_addresses(
    wallet_id: str,
    start_address_index: int,
    end_address_index: int,
    change_address=False,
) -> list[Address]:
    if start_address_index > end_address_index:
        return []

    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or not wallet.onchain_wallet_kind:
        return []

    branch_index = 1 if change_address else 0

    for address_index in range(start_address_index, end_address_index):
        address = await derive_address(
            wallet.onchain_meta.masterpub, address_index, branch_index
        )
        assert address  # TODO: why optional

        addr = Address(
            id=urlsafe_short_hash(),
            address=address,
            wallet=wallet_id,
            branch_index=branch_index,
            address_index=address_index,
        )

        async with db.connect() as conn:
            await conn.conn.execute(
                text(f"""
                    INSERT INTO onchain_addresses ({ADDRESS_COLUMNS})
                    SELECT :id, :address, :wallet, :amount, :branch_index,
                        :address_index, :note, :has_activity
                    FROM wallets WHERE id = :wallet AND wallet_type = 'onchain'
                        AND onchain_wallet_kind IS NOT NULL
                        AND {MASTERPUB_SQL} = :masterpub
                    ON CONFLICT(wallet, branch_index, address_index) DO NOTHING
                """),  # noqa: S608
                {**model_to_dict(addr), "masterpub": wallet.onchain_meta.masterpub},
            )
            await conn.conn.commit()

    # return fresh addresses
    return await db.fetchall(
        f"""
            SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE wallet = :wallet
            AND branch_index = :branch_index
            AND address_index >= :start_address_index
            AND address_index < :end_address_index
            ORDER BY branch_index, address_index
        """,  # noqa: S608
        {
            "wallet": wallet_id,
            "branch_index": branch_index,
            "start_address_index": start_address_index,
            "end_address_index": end_address_index,
        },
        Address,
    )


async def get_address(address: str) -> Address | None:
    return await db.fetchone(
        f"SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE address = :address",  # noqa: S608
        {"address": address},
        Address,
    )


async def get_address_by_id(address_id: str) -> Address | None:
    return await db.fetchone(
        f"SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE id = :id",  # noqa: S608
        {"id": address_id},
        Address,
    )


async def get_address_at_index(
    wallet_id: str, branch_index: int, address_index: int
) -> Address | None:
    return await db.fetchone(
        f"""
            SELECT {ADDRESS_COLUMNS} FROM onchain_addresses
            WHERE wallet = :wallet AND branch_index = :branch_index
            AND address_index = :address_index
        """,  # noqa: S608
        {
            "wallet": wallet_id,
            "branch_index": branch_index,
            "address_index": address_index,
        },
        Address,
    )


async def get_addresses(wallet_id: str) -> list[Address]:
    return await db.fetchall(
        f"""
        SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE wallet = :wallet
        ORDER BY branch_index, address_index
        """,  # noqa: S608
        {"wallet": wallet_id},
        Address,
    )


async def update_address(address: Address) -> Address:
    await db.execute(
        "UPDATE onchain_addresses SET note = :note WHERE id = :id",
        {"id": address.id, "note": address.note},
    )
    return address
