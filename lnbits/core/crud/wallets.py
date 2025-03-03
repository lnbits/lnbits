from datetime import datetime, timezone
from time import time
from typing import Optional
from uuid import uuid4

from lnbits.core.db import db
from lnbits.db import Connection
from lnbits.settings import settings

from ..models import Wallet


async def create_wallet(
    *,
    user_id: str,
    wallet_name: Optional[str] = None,
    conn: Optional[Connection] = None,
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
    conn: Optional[Connection] = None,
) -> Optional[Wallet]:
    wallet.updated_at = datetime.now(timezone.utc)
    await (conn or db).update("wallets", wallet)
    return wallet


async def delete_wallet(
    *,
    user_id: str,
    wallet_id: str,
    deleted: bool = True,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).execute(
        """
        UPDATE wallets
        SET deleted = :deleted, updated_at = :ts
        WHERE id = :wallet AND "user" = :user
        """,
        {
            "wallet": wallet_id,
            "user": user_id,
            "deleted": deleted,
            "ts": db.timestamp(int(time())),
        },
    )


async def force_delete_wallet(
    wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "DELETE FROM wallets WHERE id = :wallet",
        {"wallet": wallet_id},
    )


async def delete_wallet_by_id(
    wallet_id: str, conn: Optional[Connection] = None
) -> Optional[int]:
    result = await (conn or db).execute(
        "UPDATE wallets SET deleted = true, updated_at = :ts WHERE id = :wallet",
        {"wallet": wallet_id, "ts": db.timestamp(int(time()))},
    )
    return result.rowcount


async def remove_deleted_wallets(conn: Optional[Connection] = None) -> None:
    await (conn or db).execute("DELETE FROM wallets WHERE deleted = true")


async def delete_unused_wallets(
    time_delta: int,
    conn: Optional[Connection] = None,
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
    wallet_id: str, deleted: Optional[bool] = None, conn: Optional[Connection] = None
) -> Optional[Wallet]:
    sql = """
        SELECT *, COALESCE((
            SELECT balance FROM balances WHERE wallet_id = wallets.id
        ), 0) AS balance_msat FROM wallets
        WHERE id = :wallet
    """
    values: dict = {"wallet": wallet_id}
    if deleted is not None:
        sql += " AND deleted = :deleted"
        values["deleted"] = str(deleted).lower()

    return await (conn or db).fetchone(sql, values, Wallet)


async def get_wallets(
    user_id: str, deleted: Optional[bool] = None, conn: Optional[Connection] = None
) -> list[Wallet]:
    sql = """
        SELECT *, COALESCE((
            SELECT balance FROM balances WHERE wallet_id = wallets.id
        ), 0) AS balance_msat FROM wallets
        WHERE "user" = :user
    """
    values: dict = {"user": user_id}
    if deleted is not None:
        sql += " AND deleted = :deleted"
        values["deleted"] = str(deleted).lower()

    return await (conn or db).fetchall(sql, values, Wallet)


async def get_wallets_count():
    result = await db.execute("SELECT COUNT(*) as count FROM wallets")
    row = result.mappings().first()
    return row.get("count", 0)


async def get_wallet_for_key(
    key: str,
    conn: Optional[Connection] = None,
) -> Optional[Wallet]:
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


async def get_total_balance(conn: Optional[Connection] = None):
    result = await (conn or db).execute("SELECT SUM(balance) as balance FROM balances")
    row = result.mappings().first()
    return row.get("balance", 0) or 0
