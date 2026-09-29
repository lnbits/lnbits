from sqlalchemy import text  # type: ignore[import-untyped]

from lnbits.core.db import db
from lnbits.db import SQLITE, model_to_dict
from lnbits.helpers import urlsafe_short_hash

from .helpers import derive_address
from .models import Address, Config, ConfigDb, OnchainMeta, OnchainWallet, WalletAccount

ADDRESS_COLUMNS = ", ".join(Address.__fields__)
MASTERPUB_SQL = (
    "json_extract(onchain_meta, '$.masterpub')"
    if db.type == SQLITE
    else "CAST(onchain_meta AS JSONB)->>'masterpub'"
)


class WalletAlreadyConfiguredError(ValueError):
    def __init__(self):
        super().__init__(
            "This LNbits wallet is already configured. "
            "Create another LNbits onchain wallet to set up another Bitcoin wallet."
        )


async def create_watch_wallet(
    wallet: WalletAccount, encrypted_seed: str | None = None
) -> WalletAccount:
    if wallet.id != wallet.wallet_id:
        raise ValueError("Onchain setup must use the LNbits wallet ID")
    meta = OnchainMeta.parse_raw(wallet.meta)
    meta.masterpub = wallet.masterpub
    meta.fingerprint = wallet.fingerprint
    meta.script_type = wallet.type
    meta.sync_checked_at = 0
    meta.sync_error = None
    # One conditional write stores setup and recovery material together and
    # protects against competing setup requests or a concurrent network change.
    async with db.connect() as conn:
        result = await conn.conn.execute(
            text("""
                UPDATE wallets SET name = :title, onchain_meta = :meta,
                    onchain_network = :network, onchain_wallet_kind = :kind,
                    onchain_address_no = -1, onchain_backup_confirmed = false,
                    onchain_encrypted_seed = :seed, onchain_sync_lease_until = 0
                WHERE id = :id AND wallet_type = 'onchain' AND deleted = false
                    AND onchain_wallet_kind IS NULL
                    AND COALESCE(onchain_network, 'Mainnet') = :network
            """),
            {
                "id": wallet.id,
                "title": wallet.title,
                "meta": meta.json(by_alias=True),
                "network": wallet.network,
                "kind": wallet.wallet_kind,
                "seed": encrypted_seed,
            },
        )
        await conn.conn.commit()
    if result.rowcount != 1:
        if await get_watch_wallet(wallet.id):
            raise WalletAlreadyConfiguredError()
        raise ValueError("Onchain wallet or network changed during setup")
    configured = await get_watch_wallet(wallet.id)
    assert configured
    return configured


async def get_watch_wallet(wallet_id: str) -> WalletAccount | None:
    wallet = await db.fetchone(
        """
        SELECT id, name, onchain_meta, onchain_network, onchain_wallet_kind,
            onchain_address_no, onchain_backup_confirmed,
            COALESCE((SELECT SUM(amount) FROM (
                SELECT MAX(amount) AS amount FROM onchain_addresses
                WHERE wallet = wallets.id GROUP BY address
            ) coins), 0) AS balance
        FROM wallets WHERE id = :id AND wallet_type = 'onchain'
            AND onchain_wallet_kind IS NOT NULL
        """,
        {"id": wallet_id},
        OnchainWallet,
    )
    return wallet.account() if wallet else None


async def get_watch_wallets(wallet_id: str, network: str) -> list[WalletAccount]:
    wallet = await get_watch_wallet(wallet_id)
    return [wallet] if wallet and wallet.network == network else []


async def update_watch_wallet(wallet: WalletAccount) -> WalletAccount:
    # Backup confirmation must not rewrite descriptor, seed, or scanner metadata.
    await db.execute(
        """UPDATE wallets SET onchain_backup_confirmed = :confirmed
        WHERE id = :id AND wallet_type = 'onchain' AND onchain_wallet_kind = 'hot'""",
        {"id": wallet.id, "confirmed": wallet.backup_confirmed},
    )
    updated = await get_watch_wallet(wallet.id)
    assert updated
    return updated


async def delete_watch_wallet(wallet_id: str) -> None:
    async with db.connect() as conn:
        async with conn.conn.begin():
            result = await conn.conn.execute(
                text("""
                    UPDATE wallets SET onchain_meta = '{}', onchain_config = '{}',
                        onchain_network = NULL, onchain_wallet_kind = NULL,
                        onchain_address_no = -1, onchain_backup_confirmed = false,
                        onchain_sync_lease_until = 0
                    WHERE id = :id AND wallet_type = 'onchain'
                        AND onchain_wallet_kind = 'watch'
                        AND onchain_encrypted_seed IS NULL
                """),
                {"id": wallet_id},
            )
            if result.rowcount != 1:
                raise ValueError("Onchain wallet cannot be removed")
            await conn.conn.execute(
                text("DELETE FROM onchain_addresses WHERE wallet = :id"),
                {"id": wallet_id},
            )


async def get_fresh_address(wallet_id: str) -> Address | None:
    # todo: move logic to views_api after satspay refactoring
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
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
            {"wallet": wallet_id, "masterpub": wallet.masterpub},
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

    wallet = await get_watch_wallet(wallet_id)
    if not wallet:
        return []

    branch_index = 1 if change_address else 0

    for address_index in range(start_address_index, end_address_index):
        address = await derive_address(wallet.masterpub, address_index, branch_index)
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
                {**model_to_dict(addr), "masterpub": wallet.masterpub},
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


async def update_config(config: Config, wallet_id: str) -> Config:
    result = await db.execute(
        """UPDATE wallets SET onchain_config = :config, onchain_network = :network
        WHERE id = :id AND wallet_type = 'onchain'
            AND (onchain_wallet_kind IS NULL OR onchain_network = :network)""",
        {
            "id": wallet_id,
            "config": config.json(exclude={"network"}),
            "network": config.network,
        },
    )
    if result.rowcount != 1:
        raise ValueError(
            "Create another LNbits wallet to use a different Bitcoin network"
        )
    return config


async def get_config(wallet_id: str) -> Config:
    _config = await db.fetchone(
        """SELECT onchain_config, onchain_network FROM wallets
        WHERE id = :wallet_id AND wallet_type = 'onchain'""",
        {"wallet_id": wallet_id},
        ConfigDb,
    )
    if not _config:
        raise ValueError("Onchain wallet not found")
    return _config.onchain_config.copy(update={"network": _config.onchain_network})
