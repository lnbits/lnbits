from datetime import datetime, timezone
from time import time
from typing import Optional
from uuid import uuid4

from lnbits.core.crud.extensions import get_user_active_extensions_ids
from lnbits.core.crud.wallets import get_wallets
from lnbits.core.db import db
from lnbits.db import Connection, Filters, Page

from ..models import (
    Account,
    AccountFilters,
    AccountOverview,
    User,
)


async def create_account(
    account: Optional[Account] = None,
    conn: Optional[Connection] = None,
) -> Account:
    if account:
        account.validate_fields()
    else:
        now = datetime.now(timezone.utc)
        account = Account(id=uuid4().hex, created_at=now, updated_at=now)
    await (conn or db).insert("accounts", account)
    return account


async def update_account(account: Account) -> Account:
    account.updated_at = datetime.now(timezone.utc)
    await db.update("accounts", account)
    return account


async def delete_account(user_id: str, conn: Optional[Connection] = None) -> None:
    await (conn or db).execute(
        "DELETE from accounts WHERE id = :user",
        {"user": user_id},
    )


async def get_accounts(
    filters: Optional[Filters[AccountFilters]] = None,
    conn: Optional[Connection] = None,
) -> Page[AccountOverview]:
    return await (conn or db).fetch_page(
        """
        SELECT
            accounts.id,
            accounts.username,
            accounts.email,
            accounts.pubkey,
            wallets.id as wallet_id,
            SUM(COALESCE((
                SELECT balance FROM balances WHERE wallet_id = wallets.id
            ), 0)) as balance_msat,
            SUM((
                SELECT COUNT(*) FROM apipayments WHERE wallet_id = wallets.id
            )) as transaction_count,
            (
                SELECT COUNT(*) FROM wallets WHERE wallets.user = accounts.id
            ) as wallet_count,
            MAX((
                SELECT time FROM apipayments
                WHERE wallet_id = wallets.id ORDER BY time DESC LIMIT 1
            )) as last_payment
            FROM accounts LEFT JOIN wallets ON accounts.id = wallets.user
        """,
        [],
        {},
        filters=filters,
        model=AccountOverview,
        group_by=["accounts.id"],
    )


async def get_account(
    user_id: str, conn: Optional[Connection] = None
) -> Optional[Account]:
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE id = :id",
        {"id": user_id},
        Account,
    )


async def delete_accounts_no_wallets(
    time_delta: int,
    conn: Optional[Connection] = None,
) -> None:
    delta = int(time()) - time_delta
    await (conn or db).execute(
        f"""
        DELETE FROM accounts
        WHERE NOT EXISTS (
            SELECT wallets.id FROM wallets WHERE wallets.user = accounts.id
        ) AND (
            (updated_at is null AND created_at < :delta)
            OR updated_at < {db.timestamp_placeholder("delta")}
        )
        """,
        {"delta": delta},
    )


async def get_account_by_username(
    username: str, conn: Optional[Connection] = None
) -> Optional[Account]:
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE username = :username",
        {"username": username},
        Account,
    )


async def get_account_by_pubkey(
    pubkey: str, conn: Optional[Connection] = None
) -> Optional[Account]:
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE pubkey = :pubkey",
        {"pubkey": pubkey},
        Account,
    )


async def get_account_by_email(
    email: str, conn: Optional[Connection] = None
) -> Optional[Account]:
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE email = :email",
        {"email": email},
        Account,
    )


async def get_account_by_username_or_email(
    username_or_email: str, conn: Optional[Connection] = None
) -> Optional[Account]:
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE email = :value or username = :value",
        {"value": username_or_email},
        Account,
    )


async def get_user(user_id: str, conn: Optional[Connection] = None) -> Optional[User]:
    account = await get_account(user_id, conn)
    if not account:
        return None
    return await get_user_from_account(account, conn)


async def get_user_from_account(
    account: Account, conn: Optional[Connection] = None
) -> Optional[User]:
    extensions = await get_user_active_extensions_ids(account.id, conn)
    wallets = await get_wallets(account.id, False, conn=conn)
    return User(
        id=account.id,
        email=account.email,
        username=account.username,
        pubkey=account.pubkey,
        extra=account.extra,
        created_at=account.created_at,
        updated_at=account.updated_at,
        extensions=extensions,
        wallets=wallets,
        admin=account.is_admin,
        super_user=account.is_super_user,
        has_password=account.password_hash is not None,
    )
