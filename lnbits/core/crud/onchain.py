import json

from lnbits.core.crud.wallets import get_onchain_wallet
from lnbits.core.db import db
from lnbits.core.models.onchain import Address, Snapshot
from lnbits.db import Connection, model_to_dict
from lnbits.helpers import urlsafe_short_hash
from lnbits.utils.onchain import derive_address

ADDRESS_COLUMNS = ", ".join(Address.__fields__)


async def create_address(address: Address, conn: Connection | None = None) -> None:
    await (conn or db).execute(
        f"""
            INSERT INTO onchain_addresses ({ADDRESS_COLUMNS})
            SELECT :id, :address, :walet_id, :amount, :branch_index,
                :address_index, :note, :has_activity
            FROM wallets WHERE id = :walet_id AND wallet_type = 'onchain'
                AND onchain_wallet_kind IS NOT NULL
            ON CONFLICT(walet_id, branch_index, address_index) DO NOTHING
        """,  # noqa: S608
        model_to_dict(address),
    )


async def create_fresh_addresses(
    wallet_id: str,
    start_address_index: int,
    end_address_index: int,
    change_address=False,
    conn: Connection | None = None,
) -> list[Address]:
    if start_address_index > end_address_index:
        return []

    wallet = await get_onchain_wallet(wallet_id, conn=conn)
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
            walet_id=wallet_id,
            branch_index=branch_index,
            address_index=address_index,
        )

        await create_address(addr, conn=conn)

    # return fresh addresses
    return await (conn or db).fetchall(
        f"""
            SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE walet_id = :walet_id
            AND branch_index = :branch_index
            AND address_index >= :start_address_index
            AND address_index < :end_address_index
            ORDER BY branch_index, address_index
        """,  # noqa: S608
        {
            "walet_id": wallet_id,
            "branch_index": branch_index,
            "start_address_index": start_address_index,
            "end_address_index": end_address_index,
        },
        Address,
    )


async def get_address(address: str, conn: Connection | None = None) -> Address | None:
    return await (conn or db).fetchone(
        f"SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE address = :address",  # noqa: S608
        {"address": address},
        Address,
    )


async def get_address_by_id(
    address_id: str, conn: Connection | None = None
) -> Address | None:
    return await (conn or db).fetchone(
        f"SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE id = :id",  # noqa: S608
        {"id": address_id},
        Address,
    )


async def get_address_at_index(
    wallet_id: str,
    branch_index: int,
    address_index: int,
    conn: Connection | None = None,
) -> Address | None:
    return await (conn or db).fetchone(
        f"""
            SELECT {ADDRESS_COLUMNS} FROM onchain_addresses
            WHERE walet_id = :walet_id AND branch_index = :branch_index
            AND address_index = :address_index
        """,  # noqa: S608
        {
            "walet_id": wallet_id,
            "branch_index": branch_index,
            "address_index": address_index,
        },
        Address,
    )


async def get_last_used_address_index(
    wallet_id: str, conn: Connection | None = None
) -> int:
    last_used: dict = await (conn or db).fetchone(
        """SELECT COALESCE(MAX(address_index), -1) AS address_index
        FROM onchain_addresses WHERE walet_id = :walet_id
            AND branch_index = 0 AND has_activity = true""",
        {"walet_id": wallet_id},
    )
    return last_used["address_index"]


async def get_addresses(
    wallet_id: str, conn: Connection | None = None
) -> list[Address]:
    return await (conn or db).fetchall(
        f"""
        SELECT {ADDRESS_COLUMNS} FROM onchain_addresses WHERE walet_id = :walet_id
        ORDER BY branch_index, address_index
        """,  # noqa: S608
        {"walet_id": wallet_id},
        Address,
    )


async def update_address(address: Address, conn: Connection | None = None) -> Address:
    await (conn or db).execute(
        "UPDATE onchain_addresses SET note = :note WHERE id = :id",
        {"id": address.id, "note": address.note},
    )
    return address


async def get_address_snapshot(
    address_id: str, conn: Connection | None = None
) -> Snapshot | None:
    return await (conn or db).fetchone(
        """SELECT id AS address_id, transactions, utxos,
            snapshot_checked_at AS checked_at
        FROM onchain_addresses WHERE id = :id""",
        {"id": address_id},
        Snapshot,
    )


async def get_wallet_snapshots(
    wallet_id: str, conn: Connection | None = None
) -> list[Snapshot]:
    return await (conn or db).fetchall(
        """SELECT id AS address_id, transactions, utxos,
            snapshot_checked_at AS checked_at
        FROM onchain_addresses WHERE walet_id = :wallet AND snapshot_checked_at > 0""",
        {"wallet": wallet_id},
        Snapshot,
    )


async def update_address_snapshot(
    snapshot: Snapshot, amount: int, conn: Connection | None = None
) -> None:
    # Update only: an in-flight scan must not recreate a removed address.
    await (conn or db).execute(
        """UPDATE onchain_addresses SET transactions = :transactions,
            utxos = :utxos, snapshot_checked_at = :now, amount = :amount,
            has_activity = has_activity OR :active WHERE id = :id""",
        {
            "id": snapshot.address_id,
            "transactions": json.dumps(snapshot.transactions),
            "utxos": json.dumps(snapshot.utxos),
            "now": snapshot.checked_at,
            "amount": amount,
            "active": bool(snapshot.transactions),
        },
    )
