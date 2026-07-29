from datetime import datetime, timezone
from time import time
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from lnbits.core.db import db
from lnbits.core.models.wallets import BaseWallet, WalletsFilters, WalletType
from lnbits.db import Connection, Database, Filters, Page
from lnbits.helpers import generate_ln_address
from lnbits.settings import settings
from lnbits.utils.cache import cache

from ..models import Wallet

_LEGACY_LNURLP_DB = Database("ext_lnurlp")


async def create_wallet(
    *,
    user_id: str,
    wallet_name: str | None = None,
    wallet_type: WalletType = WalletType.LIGHTNING,
    shared_wallet_id: str | None = None,
    conn: Connection | None = None,
) -> Wallet:
    wallet_id = uuid4().hex
    wallet = Wallet(
        id=wallet_id,
        name=wallet_name or settings.lnbits_default_wallet_name,
        wallet_type=wallet_type.value,
        shared_wallet_id=shared_wallet_id,
        user=user_id,
        adminkey=uuid4().hex,
        inkey=uuid4().hex,
        currency=settings.lnbits_default_accounting_currency or "USD",
    )
    if settings.lnbits_enable_wallet_lightning_addresses and wallet.is_lightning_wallet:
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
        """
        DELETE FROM wallets
        WHERE (
            SELECT COUNT(*) FROM apipayments WHERE wallet_id = wallets.id
        ) = 0 AND (
            (updated_at is null AND created_at < :delta)
            OR updated_at < :delta
        )
        """,
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
    from ..services.lightning_address import ensure_wallet_lightning_address

    return await ensure_wallet_lightning_address(wallet, conn)


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
    query = """SELECT * FROM wallets WHERE "user" = :user"""
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


async def legacy_lnurlp_address_exists(local_part: str) -> bool:
    try:
        row: Any = await _LEGACY_LNURLP_DB.fetchone(
            """
            SELECT 1 FROM lnurlp.pay_links
            WHERE username = :username
            LIMIT 1
            """,
            {"username": local_part},
        )
        return row is not None
    except OperationalError:
        return False
    except Exception:
        return False


async def generate_lightning_address_local_part(
    conn: Connection | None = None,
) -> str:
    for _ in range(100):
        local_part = generate_ln_address()
        if await get_wallet_id_by_ln_address(local_part, conn):
            continue
        if await legacy_lnurlp_address_exists(local_part):
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


async def get_total_balance(conn: Connection | None = None):
    result = await (conn or db).execute("SELECT SUM(balance) as balance FROM balances")
    row = result.mappings().first()
    return row.get("balance", 0) or 0


def clear_wallet_id_cache(wallet_id: str):
    cached_wallet: BaseWallet | None = cache.pop(f"auth:wallet:{wallet_id}")
    if cached_wallet:
        cache.pop(f"auth:x-api-key:{cached_wallet.adminkey}")
        cache.pop(f"auth:x-api-key:{cached_wallet.inkey}")


def clear_wallet_cache(wallet: Wallet):
    cache.pop(f"auth:wallet:{wallet.id}")
    cache.pop(f"auth:x-api-key:{wallet.adminkey}")
    cache.pop(f"auth:x-api-key:{wallet.inkey}")
