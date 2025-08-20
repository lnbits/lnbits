from datetime import datetime, timezone
from time import time
from uuid import uuid4

from lnbits.core.db import db
from lnbits.core.models.wallets import WalletsFilters
from lnbits.db import Connection, Filters, Page
from lnbits.settings import settings

from ..models import Wallet


async def create_wallet(
    *,
    user_id: str,
    wallet_name: str | None = None,
    conn: Connection | None = None,
) -> Wallet:
    wallet_id = uuid4().hex
    wallet = Wallet(
        id=wallet_id,
        name=wallet_name or settings.lnbits_default_wallet_name,
        user=user_id,
        adminkey=uuid4().hex,
        inkey=uuid4().hex,
        currency=settings.lnbits_default_accounting_currency or "USD",
    )
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
    *,
    user_id: str,
    wallet_id: str,
    deleted: bool = True,
    conn: Connection | None = None,
) -> None:
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
    await (conn or db).execute(
        "DELETE FROM wallets WHERE id = :wallet",
        {"wallet": wallet_id},
    )


async def delete_wallet_by_id(
    wallet_id: str, conn: Connection | None = None
) -> int | None:
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


async def get_wallet(
    wallet_id: str, deleted: bool | None = None, conn: Connection | None = None
) -> Wallet | None:
    query = """
            SELECT *, COALESCE((
                SELECT balance FROM balances WHERE wallet_id = wallets.id
            ), 0) AS balance_msat FROM wallets
            WHERE id = :wallet
            """
    if deleted is not None:
        query += " AND deleted = :deleted "
    return await (conn or db).fetchone(
        query,
        {"wallet": wallet_id, "deleted": deleted},
        Wallet,
    )


async def get_wallets(
    user_id: str, deleted: bool | None = None, conn: Connection | None = None
) -> list[Wallet]:
    query = """
            SELECT *, COALESCE((
                SELECT balance FROM balances WHERE wallet_id = wallets.id
            ), 0) AS balance_msat FROM wallets
            WHERE "user" = :user
            """
    if deleted is not None:
        query += " AND deleted = :deleted "
    return await (conn or db).fetchall(
        query,
        {"user": user_id, "deleted": deleted},
        Wallet,
    )


async def get_wallets_paginated(
    user_id: str,
    deleted: bool | None = None,
    filters: Filters[WalletsFilters] | None = None,
    conn: Connection | None = None,
) -> Page[Wallet]:
    if deleted is None:
        deleted = False

    where: list[str] = [""" "user" = :user AND deleted = :deleted """]
    return await (conn or db).fetch_page(
        """
            SELECT *, COALESCE((
                SELECT balance FROM balances WHERE wallet_id = wallets.id
            ), 0) AS balance_msat FROM wallets
        """,
        where=where,
        values={"user": user_id, "deleted": deleted},
        filters=filters,
        model=Wallet,
    )


async def get_wallets_ids(
    user_id: str, deleted: bool | None = None, conn: Connection | None = None
) -> list[str]:
    query = """SELECT id FROM wallets  WHERE "user" = :user"""
    if deleted is not None:
        query += "AND deleted = :deleted"
    result: list[dict] = await (conn or db).fetchall(
        query,
        {"user": user_id, "deleted": deleted},
    )
    return [row["id"] for row in result]


async def get_wallets_count():
    result = await db.execute("SELECT COUNT(*) as count FROM wallets")
    row = result.mappings().first()
    return row.get("count", 0)


async def get_wallet_for_key(
    key: str,
    conn: Connection | None = None,
) -> Wallet | None:
    return await (conn or db).fetchone(
        """
        SELECT *, COALESCE((
            SELECT balance FROM balances WHERE wallet_id = wallets.id
        ), 0)
        AS balance_msat FROM wallets
        WHERE (adminkey = :key OR inkey = :key) AND deleted = false
        """,
        {"key": key},
        Wallet,
    )


async def get_total_balance(conn: Connection | None = None):
    result = await (conn or db).execute("SELECT SUM(balance) as balance FROM balances")
    row = result.mappings().first()
    return row.get("balance", 0) or 0
