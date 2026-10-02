import json
from datetime import datetime, timezone
from time import time
from typing import Literal
from uuid import uuid4

from lnbits.core.db import db
from lnbits.core.models.wallets import (
    BaseWallet,
    OnchainConfig,
    OnchainWallet,
    WalletsFilters,
    WalletType,
)
from lnbits.db import SQLITE, Connection, Filters, Page
from lnbits.helpers import generate_ln_address
from lnbits.settings import settings
from lnbits.utils.cache import cache
from lnbits.utils.exchange_rates import allowed_currencies

from ..models import Wallet


class WalletAlreadyConfiguredError(ValueError):
    def __init__(self):
        super().__init__(
            "This LNbits wallet is already configured. "
            "Create another LNbits onchain wallet to set up another Bitcoin wallet."
        )


async def create_wallet(
    *,
    user_id: str,
    wallet_name: str | None = None,
    wallet_type: WalletType = WalletType.LIGHTNING,
    currency: str | None = None,
    shared_wallet_id: str | None = None,
    onchain_network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet",
    conn: Connection | None = None,
) -> Wallet:
    if currency is not None:
        currency = currency.upper()
        if currency not in allowed_currencies():
            raise ValueError("The provided currency is not supported")
    else:
        currency = settings.lnbits_default_accounting_currency or "USD"
    wallet_id = uuid4().hex
    wallet = Wallet(
        id=wallet_id,
        name=wallet_name or settings.lnbits_default_wallet_name,
        wallet_type=wallet_type.value,
        shared_wallet_id=shared_wallet_id,
        onchain_network=onchain_network if wallet_type == WalletType.ONCHAIN else None,
        user=user_id,
        adminkey=uuid4().hex,
        inkey=uuid4().hex,
        currency=currency,
    )
    if wallet_type == WalletType.ONCHAIN:
        wallet.extra.icon = "currency_bitcoin"
    if wallet_type == WalletType.FIAT:
        wallet.extra.icon = "credit_card"
    if settings.ln_address_creation_allowed and wallet.is_lightning_wallet:
        wallet.lightning_address = await generate_lightning_address_local_part(conn)

    await (conn or db).insert("wallets", wallet)
    return wallet


async def update_wallet(
    wallet: Wallet,
    conn: Connection | None = None,
) -> Wallet:
    wallet.updated_at = datetime.now(timezone.utc)
    await (conn or db).update("wallets", wallet)
    return wallet


async def delete_wallet(
    user_id: str,
    wallet_id: str,
    deleted: bool = True,
    conn: Connection | None = None,
) -> None:
    clear_wallet_id_cache(wallet_id)
    now = int(time())

    await (conn or db).execute(
        # Timestamp placeholder is safe from SQL injection (not user input)
        f"""
        UPDATE wallets
        SET deleted = :deleted, updated_at = {db.timestamp_placeholder('now')}
        WHERE id = :wallet AND "user" = :user
        """,  # noqa: S608
        {"wallet": wallet_id, "user": user_id, "deleted": deleted, "now": now},
    )


async def force_delete_wallet(wallet_id: str, conn: Connection | None = None) -> None:
    clear_wallet_id_cache(wallet_id)

    await (conn or db).execute(
        "DELETE FROM wallets WHERE id = :wallet",
        {"wallet": wallet_id},
    )


async def delete_wallet_by_id(
    wallet_id: str, conn: Connection | None = None
) -> int | None:
    clear_wallet_id_cache(wallet_id)
    now = int(time())
    result = await (conn or db).execute(
        # Timestamp placeholder is safe from SQL injection (not user input)
        f"""
        UPDATE wallets
        SET deleted = true, updated_at = {db.timestamp_placeholder('now')}
        WHERE id = :wallet
        """,  # noqa: S608
        {"wallet": wallet_id, "now": now},
    )
    return result.rowcount


async def remove_deleted_wallets(conn: Connection | None = None) -> None:
    await (conn or db).execute("DELETE FROM wallets WHERE deleted = true")


async def delete_unused_wallets(
    time_delta: int,
    conn: Connection | None = None,
) -> None:
    delta = int(time()) - time_delta
    await (conn or db).execute(
        f"""
        DELETE FROM wallets
        WHERE (
            SELECT COUNT(*) FROM apipayments WHERE wallet_id = wallets.id
        ) = 0 AND (
            (updated_at is null AND created_at < {db.timestamp_placeholder('delta')})
            OR updated_at < {db.timestamp_placeholder('delta')}
        )
        """,  # noqa: S608
        {"delta": delta},
    )


async def get_standalone_wallet(
    wallet_id: str, deleted: bool | None = False, conn: Connection | None = None
) -> Wallet | None:
    query = """
            SELECT *, COALESCE((
                SELECT balance FROM balances WHERE wallet_id = wallets.id
            ), 0) AS balance_msat FROM wallets
            WHERE id = :wallet
            """
    if deleted is not None:
        query += " AND deleted = :deleted "
    wallet = await (conn or db).fetchone(
        query,
        {"wallet": wallet_id, "deleted": deleted},
        Wallet,
    )
    if not wallet:
        return None
    if deleted is True:
        return wallet

    if (
        wallet.is_lightning_wallet
        and not wallet.lightning_address
        and settings.ln_address_creation_allowed
    ):
        wallet.lightning_address = await generate_lightning_address_local_part(conn)
        await update_wallet(wallet, conn)

    return wallet


async def get_wallet(
    wallet_id: str, deleted: bool | None = False, conn: Connection | None = None
) -> Wallet | None:
    wallet = await get_standalone_wallet(wallet_id, deleted, conn)
    if not wallet:
        return None
    if wallet.is_lightning_shared_wallet:
        return await get_source_wallet(wallet, conn)

    return wallet


async def get_wallets(
    user_id: str,
    deleted: bool | None = False,
    wallet_type: WalletType | None = None,
    conn: Connection | None = None,
) -> list[Wallet]:
    query = """
            SELECT *, COALESCE((
                SELECT balance FROM balances WHERE wallet_id = wallets.id
            ), 0) AS balance_msat FROM wallets
            WHERE "user" = :user
            """
    if deleted is not None:
        query += " AND deleted = :deleted "
    if wallet_type is not None:
        query += " AND wallet_type = :wallet_type "
    wallets = await (conn or db).fetchall(
        query,
        {
            "user": user_id,
            "deleted": deleted,
            "wallet_type": wallet_type.value if wallet_type else None,
        },
        Wallet,
    )

    return await get_source_wallets(wallets, conn)


async def get_wallets_paginated(
    user_id: str,
    deleted: bool | None = None,
    filters: Filters[WalletsFilters] | None = None,
    conn: Connection | None = None,
) -> Page[Wallet]:
    if deleted is None:
        deleted = False

    where: list[str] = [""" "user" = :user AND deleted = :deleted """]
    wallets = await (conn or db).fetch_page(
        """
            SELECT *, COALESCE((
                SELECT balance FROM balances WHERE wallet_id = wallets.id
            ), 0) AS balance_msat FROM wallets
        """,
        where=where,
        values={"user": user_id, "deleted": deleted},
        filters=filters,
        model=Wallet,
        table_name="wallets",
    )

    wallets.data = await get_source_wallets(wallets.data, conn)
    return wallets


async def get_wallets_ids(
    user_id: str, deleted: bool | None = False, conn: Connection | None = None
) -> list[str]:
    query = 'SELECT * FROM wallets WHERE "user" = :user'
    if deleted is not None:
        query += " AND deleted = :deleted "
    wallets = await (conn or db).fetchall(
        query,
        {"user": user_id, "deleted": deleted},
        Wallet,
    )

    wallets = await get_source_wallets(wallets, conn)
    return [w.source_wallet_id for w in wallets if w.can_view_payments]


async def get_wallets_count():
    result = await db.execute("SELECT COUNT(*) as count FROM wallets")
    row = result.mappings().first()
    return row.get("count", 0)


async def generate_lightning_address_local_part(
    conn: Connection | None = None,
) -> str:
    for _ in range(100):
        local_part = generate_ln_address()
        if await get_wallet_id_by_ln_address(local_part, conn):
            continue
        return local_part
    raise ValueError("Could not generate a unique wallet lightning address.")


async def get_wallet_id_by_ln_address(
    local_part: str, conn: Connection | None = None
) -> str | None:
    row: dict = await (conn or db).fetchone(
        """
        SELECT id FROM wallets
        WHERE lightning_address = :lightning_address
        """,
        {"lightning_address": local_part.lower()},
    )
    return row["id"] if row else None


async def get_wallet_for_key(
    key: str,
    conn: Connection | None = None,
) -> Wallet | None:
    wallet = await (conn or db).fetchone(
        """
        SELECT wallets.*, COALESCE((
            SELECT balance FROM balances WHERE wallet_id = wallets.id
        ), 0)
        AS balance_msat FROM wallets
        INNER JOIN accounts ON wallets.user = accounts.id
        WHERE (adminkey = :key OR inkey = :key)
            AND deleted = false
            AND accounts.activated = true
        """,
        {"key": key},
        Wallet,
    )
    if not wallet:
        return None

    if wallet.is_lightning_shared_wallet:
        mw = await get_source_wallet(wallet, conn)
        return mw
    return wallet


async def get_base_wallet_for_key(
    key: str,
    conn: Connection | None = None,
) -> BaseWallet | None:
    wallet = await (conn or db).fetchone(
        """
        SELECT wallets.id, "user", wallet_type, adminkey, inkey FROM wallets
        INNER JOIN accounts ON wallets.user = accounts.id
        WHERE (adminkey = :key OR inkey = :key)
            AND deleted = false
            AND accounts.activated = true
        """,
        {"key": key},
        BaseWallet,
    )
    if not wallet:
        return None

    return wallet


async def get_source_wallet(
    wallet: Wallet, conn: Connection | None = None
) -> Wallet | None:
    if not wallet.is_lightning_shared_wallet:
        return wallet
    if not wallet.shared_wallet_id:
        return None

    shared_wallet = await get_standalone_wallet(wallet.shared_wallet_id, False, conn)
    if not shared_wallet:
        return None
    wallet.mirror_shared_wallet(shared_wallet)
    return wallet


async def get_source_wallets(
    wallet: list[Wallet], conn: Connection | None = None
) -> list[Wallet]:
    source_wallets = []
    for w in wallet:
        source_wallet = await get_source_wallet(w, conn)
        if source_wallet:
            source_wallets.append(source_wallet)
    return source_wallets


async def get_total_balance(conn: Connection | None = None, *, fiat: bool = False):
    result = await (conn or db).execute(
        """
        SELECT SUM(balance) as balance FROM balances
        JOIN wallets ON wallets.id = balances.wallet_id
        WHERE wallets.wallet_type = :wallet_type
        """,
        {"wallet_type": "fiat" if fiat else "lightning"},
    )
    row = result.mappings().first()
    return row.get("balance", 0) or 0


async def init_onchain_wallet_state(
    wallet: OnchainWallet,
    encrypted_seed: str | None = None,
    conn: Connection | None = None,
) -> OnchainWallet:
    meta = wallet.onchain_meta.copy()
    meta.sync_checked_at = 0
    meta.sync_error = None
    # One conditional write stores setup and recovery material together and
    # protects against competing setup requests.
    result = await (conn or db).execute(
        """UPDATE wallets SET name = :title, onchain_meta = :meta,
            onchain_network = :network, onchain_wallet_kind = :kind,
            onchain_address_no = -1, onchain_backup_confirmed = false,
            onchain_encrypted_seed = :seed, onchain_sync_lease_until = 0
        WHERE id = :id AND wallet_type = 'onchain' AND deleted = false
            AND onchain_wallet_kind IS NULL""",
        {
            "id": wallet.id,
            "title": wallet.name,
            "meta": meta.json(by_alias=True),
            "network": wallet.onchain_network,
            "kind": wallet.onchain_wallet_kind,
            "seed": encrypted_seed,
        },
    )
    if result.rowcount != 1:
        existing = await get_onchain_wallet(wallet.id, conn=conn)
        if existing and existing.onchain_wallet_kind:
            raise WalletAlreadyConfiguredError()
        raise ValueError("Onchain wallet is unavailable for setup")
    configured = await get_onchain_wallet(wallet.id, conn=conn)
    assert configured
    return configured


async def get_onchain_wallet(
    wallet_id: str, deleted: bool | None = False, conn: Connection | None = None
) -> OnchainWallet | None:
    query = """
        SELECT *, COALESCE((SELECT balance FROM balances
            WHERE wallet_id = wallets.id), 0) AS balance_msat
        FROM wallets WHERE id = :id AND wallet_type = 'onchain'
        """
    if deleted is not None:
        query += " AND deleted = :deleted "
    return await (conn or db).fetchone(
        query,
        {"id": wallet_id, "deleted": deleted},
        OnchainWallet,
    )


async def get_onchain_encrypted_seed(
    wallet_id: str, conn: Connection | None = None
) -> str | None:
    row: dict = await (conn or db).fetchone(
        """SELECT onchain_encrypted_seed AS encrypted_seed FROM wallets
        WHERE id = :wallet AND wallet_type = 'onchain'
            AND onchain_wallet_kind = 'hot' AND onchain_encrypted_seed IS NOT NULL""",
        {"wallet": wallet_id},
    )
    return row["encrypted_seed"] if row else None


async def reserve_onchain_address_index(
    wallet_id: str,
    index: int,
    previous_index: int,
    conn: Connection | None = None,
) -> bool:
    result = await (conn or db).execute(
        """
        UPDATE wallets SET onchain_address_no = :index
        WHERE id = :walet_id AND wallet_type = 'onchain'
            AND onchain_wallet_kind IS NOT NULL
            AND onchain_address_no = :previous_index
        """,
        {
            "walet_id": wallet_id,
            "index": index,
            "previous_index": previous_index,
        },
    )
    return result.rowcount == 1


async def update_onchain_wallet(
    wallet: OnchainWallet, conn: Connection | None = None
) -> OnchainWallet:
    # Backup confirmation must not rewrite descriptor, seed, or scanner metadata.
    await (conn or db).execute(
        """UPDATE wallets SET onchain_backup_confirmed = :confirmed
        WHERE id = :id AND wallet_type = 'onchain' AND onchain_wallet_kind = 'hot'""",
        {"id": wallet.id, "confirmed": wallet.onchain_backup_confirmed},
    )
    updated = await get_onchain_wallet(wallet.id, conn=conn)
    assert updated
    return updated


async def clear_onchain_wallet_data(
    wallet_id: str, conn: Connection | None = None
) -> None:
    result = await (conn or db).execute(
        """
        UPDATE wallets SET onchain_meta = '{}', onchain_config = '{}',
            onchain_network = NULL, onchain_wallet_kind = NULL,
            onchain_address_no = -1, onchain_backup_confirmed = false,
            onchain_sync_lease_until = 0
        WHERE id = :id AND wallet_type = 'onchain'
            AND onchain_wallet_kind = 'watch'
            AND onchain_encrypted_seed IS NULL
        """,
        {"id": wallet_id},
    )
    if result.rowcount != 1:
        raise ValueError("Onchain wallet cannot be removed")
    await (conn or db).execute(
        "DELETE FROM onchain_addresses WHERE walet_id = :id",
        {"id": wallet_id},
    )


async def update_onchain_wallet_config(
    config: OnchainConfig,
    wallet_id: str,
    network: str | None = None,
    conn: Connection | None = None,
) -> None:
    await (conn or db).execute(
        """UPDATE wallets SET onchain_config = :config,
            onchain_network = COALESCE(:network, onchain_network, 'Mainnet')
        WHERE id = :id AND wallet_type = 'onchain'
            AND (onchain_wallet_kind IS NULL OR CAST(:network AS TEXT) IS NULL
                OR onchain_network = :network)""",
        {
            "id": wallet_id,
            "config": config.json(exclude={"network"}),
            "network": network,
        },
    )


async def acquire_onchain_scan_lease(
    wallet_id: str, lease: int, now: int, conn: Connection | None = None
) -> bool:
    acquired = await (conn or db).execute(
        """
        UPDATE wallets SET onchain_sync_lease_until = :lease
        WHERE id = :wallet AND onchain_sync_lease_until < :now
            AND wallet_type = 'onchain' AND deleted = false
            AND onchain_wallet_kind IS NOT NULL
        """,
        {"wallet": wallet_id, "lease": lease, "now": now},
    )
    return acquired.rowcount == 1


async def get_onchain_sync_status(
    wallet_id: str, conn: Connection | None = None
) -> dict:
    return (
        await (conn or db).fetchone(
            """SELECT onchain_meta, onchain_sync_lease_until FROM wallets
        WHERE id = :wallet AND wallet_type = 'onchain'""",
            {"wallet": wallet_id},
        )
        or {}
    )


async def get_onchain_wallet_ids(conn: Connection | None = None) -> list[str]:
    rows: list[dict] = await (conn or db).fetchall("""
        SELECT id FROM wallets WHERE wallet_type = 'onchain' AND deleted = false
            AND onchain_wallet_kind IS NOT NULL
    """)
    return [row["id"] for row in rows]


async def finish_scan(
    wallet_id: str, lease: int, error: str | None, conn: Connection | None = None
) -> None:
    now = int(time())
    state: dict = {"sync_error": error}
    if error is None:
        state["sync_checked_at"] = now
    # Merge only scanner-owned keys in the same conditional update that releases
    # the lease. Other metadata and newer scan leases must remain untouched.
    if db.type == SQLITE:
        expression = "json_set(onchain_meta, '$.sync_error', :error)"
        if error is None:
            expression = (
                "json_set(onchain_meta, '$.sync_error', :error, "
                "'$.sync_checked_at', :now)"
            )
    else:
        expression = (
            "CAST(CAST(onchain_meta AS JSONB) || CAST(:state AS JSONB) AS TEXT)"
        )
    await (conn or db).execute(
        f"""
        UPDATE wallets SET onchain_sync_lease_until = 0,
            onchain_meta = {expression}
        WHERE id = :wallet AND wallet_type = 'onchain'
            AND onchain_wallet_kind IS NOT NULL AND onchain_sync_lease_until = :lease
        """,  # noqa: S608
        {
            "wallet": wallet_id,
            "lease": lease,
            "error": error,
            "now": now,
            "state": json.dumps(state),
        },
    )


def clear_wallet_id_cache(wallet_id: str):
    cached_wallet: BaseWallet | None = cache.pop(f"auth:wallet:{wallet_id}")
    if cached_wallet:
        cache.pop(f"auth:x-api-key:{cached_wallet.adminkey}")
        cache.pop(f"auth:x-api-key:{cached_wallet.inkey}")


def clear_wallet_cache(wallet: Wallet):
    cache.pop(f"auth:wallet:{wallet.id}")
    cache.pop(f"auth:x-api-key:{wallet.adminkey}")
    cache.pop(f"auth:x-api-key:{wallet.inkey}")
