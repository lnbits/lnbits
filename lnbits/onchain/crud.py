from sqlalchemy import text  # type: ignore[import-untyped]
from sqlalchemy.exc import IntegrityError  # type: ignore[import-untyped]

from lnbits.core.db import db
from lnbits.db import insert_query, model_to_dict
from lnbits.helpers import urlsafe_short_hash

from .helpers import derive_address
from .models import Address, Config, ConfigDb, WalletAccount


class WalletAlreadyConfiguredError(ValueError):
    def __init__(self):
        super().__init__(
            "This LNbits wallet is already configured. "
            "Create another LNbits onchain wallet to set up another Bitcoin wallet."
        )


async def create_watch_wallet(
    wallet: WalletAccount, encrypted_seed: str | None = None
) -> WalletAccount:
    try:
        async with db.connect() as conn:
            # Keep the account and its recovery material in one transaction.
            # The unique wallet_id index also protects concurrent setup requests.
            await conn.conn.commit()
            async with conn.conn.begin():
                await conn.conn.execute(
                    text(conn.rewrite_query(insert_query("onchain_accounts", wallet))),
                    model_to_dict(wallet),
                )
                if encrypted_seed is not None:
                    await conn.conn.execute(
                        text(
                            "INSERT INTO onchain_keys (wallet, encrypted_seed) "
                            "VALUES (:wallet, :seed)"
                        ),
                        {"wallet": wallet.id, "seed": encrypted_seed},
                    )
    except IntegrityError as exc:
        existing: dict | None = await db.fetchone(
            "SELECT id FROM onchain_accounts WHERE wallet_id = :wallet",
            {"wallet": wallet.wallet_id},
        )
        if existing:
            raise WalletAlreadyConfiguredError() from exc
        raise
    return wallet


async def get_watch_wallet(wallet_id: str) -> WalletAccount | None:
    return await db.fetchone(
        "SELECT * FROM onchain_accounts WHERE id = :id",
        {"id": wallet_id},
        WalletAccount,
    )


async def get_watch_wallets(wallet_id: str, network: str) -> list[WalletAccount]:
    return await db.fetchall(
        """
        SELECT * FROM onchain_accounts
        WHERE "wallet_id" = :wallet_id AND network = :network
        """,
        {"wallet_id": wallet_id, "network": network},
        WalletAccount,
    )


async def update_watch_wallet(wallet: WalletAccount) -> WalletAccount:
    await db.update("onchain_accounts", wallet)
    return wallet


async def delete_watch_wallet(wallet_id: str) -> None:
    await db.execute(
        "DELETE FROM onchain_accounts WHERE id = :id",
        {"id": wallet_id},
    )


async def get_fresh_address(wallet_id: str) -> Address | None:
    # todo: move logic to views_api after satspay refactoring
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        return None

    # Atomically reserve an index across concurrent browsers/workers.
    async with db.connect() as conn:
        row = await conn.fetchone(
            """
            UPDATE onchain_accounts SET address_no =
                CASE WHEN address_no < COALESCE((
                    SELECT MAX(address_index) FROM onchain_addresses
                    WHERE wallet = :wallet AND branch_index = 0 AND has_activity = true
                ), -1) THEN (
                    SELECT MAX(address_index) FROM onchain_addresses
                    WHERE wallet = :wallet AND branch_index = 0 AND has_activity = true
                ) + 1 ELSE address_no + 1 END
            WHERE id = :wallet RETURNING address_no
        """,
            {"wallet": wallet_id},
        )
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

        await db.execute(
            insert_query("onchain_addresses", addr)
            + " ON CONFLICT(wallet, branch_index, address_index) DO NOTHING",
            model_to_dict(addr),
        )

    # return fresh addresses
    return await db.fetchall(
        """
            SELECT * FROM onchain_addresses WHERE wallet = :wallet
            AND branch_index = :branch_index
            AND address_index >= :start_address_index
            AND address_index < :end_address_index
            ORDER BY branch_index, address_index
        """,
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
        "SELECT * FROM onchain_addresses WHERE address = :address",
        {"address": address},
        Address,
    )


async def get_address_by_id(address_id: str) -> Address | None:
    return await db.fetchone(
        "SELECT * FROM onchain_addresses WHERE id = :id",
        {"id": address_id},
        Address,
    )


async def get_address_at_index(
    wallet_id: str, branch_index: int, address_index: int
) -> Address | None:
    return await db.fetchone(
        """
            SELECT * FROM onchain_addresses
            WHERE wallet = :wallet AND branch_index = :branch_index
            AND address_index = :address_index
        """,
        {
            "wallet": wallet_id,
            "branch_index": branch_index,
            "address_index": address_index,
        },
        Address,
    )


async def get_addresses(wallet_id: str) -> list[Address]:
    return await db.fetchall(
        """
        SELECT * FROM onchain_addresses WHERE wallet = :wallet
        ORDER BY branch_index, address_index
        """,
        {"wallet": wallet_id},
        Address,
    )


async def update_address(address: Address) -> Address:
    await db.update("onchain_addresses", address)
    return address


async def delete_addresses_for_wallet(wallet_id: str) -> None:
    await db.execute(
        "DELETE FROM onchain_addresses WHERE wallet = :wallet", {"wallet": wallet_id}
    )


async def create_config(wallet_id: str) -> Config:
    config = Config()
    model = ConfigDb(wallet_id=wallet_id, json_data=config)
    await db.execute(
        insert_query("onchain_config", model) + " ON CONFLICT(wallet_id) DO NOTHING",
        model_to_dict(model),
    )
    return config


async def update_config(config: Config, wallet_id: str) -> Config:
    _config = ConfigDb(wallet_id=wallet_id, json_data=config)
    await db.update("onchain_config", _config, """WHERE "wallet_id" = :wallet_id""")
    return config


async def get_config(wallet_id: str) -> Config:
    _config = await db.fetchone(
        """SELECT * FROM onchain_config WHERE "wallet_id" = :wallet_id""",
        {"wallet_id": wallet_id},
        ConfigDb,
    )
    if not _config:
        return await create_config(wallet_id)
    return _config.json_data
