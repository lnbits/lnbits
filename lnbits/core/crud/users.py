from datetime import datetime, timezone
from time import time
from typing import Any
from uuid import uuid4

from lnbits.core.crud.extensions import get_user_active_extensions_ids
from lnbits.core.crud.wallets import create_wallet, get_wallets
from lnbits.core.db import db
from lnbits.core.models import UserAcls
from lnbits.db import Connection, Filters, Page

from ..models import (
    Account,
    AccountFilters,
    AccountOverview,
    User,
)


async def create_account(
    account: Account | None = None,
    conn: Connection | None = None,
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


async def delete_account(user_id: str, conn: Connection | None = None) -> None:
    await (conn or db).execute(
        "DELETE from accounts WHERE id = :user",
        {"user": user_id},
    )


async def get_accounts(
    filters: Filters[AccountFilters] | None = None,
    conn: Connection | None = None,
) -> Page[AccountOverview]:
    where_clauses = []
    values: dict[str, Any] = {}

    # Make wallet filter explicit
    wallet_filter = (
        next((f for f in filters.filters if f.field == "wallet_id"), None)
        if filters
        else None
    )
    if filters and wallet_filter and wallet_filter.values:
        where_clauses.append("wallets.id = :wallet_id")
        values = {**values, "wallet_id": next(iter(wallet_filter.values.values()))}
        filters.filters = [f for f in filters.filters if f.field != "wallet_id"]

    return await (conn or db).fetch_page(
        """
        SELECT
            accounts.id,
            accounts.username,
            accounts.email,
            accounts.pubkey,
            accounts.external_id,
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
        where_clauses,
        values,
        filters=filters,
        model=AccountOverview,
        group_by=["accounts.id"],
        table_name="accounts",
    )


async def get_account(user_id: str, conn: Connection | None = None) -> Account | None:
    if len(user_id) == 0:
        return None
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE id = :id",
        {"id": user_id},
        Account,
    )


async def delete_accounts_no_wallets(
    time_delta: int,
    conn: Connection | None = None,
) -> None:
    delta = int(time()) - time_delta
    await (conn or db).execute(
        # Timestamp placeholder is safe from SQL injection (not user input)
        f"""
        DELETE FROM accounts
        WHERE NOT EXISTS (
            SELECT wallets.id FROM wallets WHERE wallets.user = accounts.id
        ) AND (
            (updated_at is null AND created_at < :delta)
            OR updated_at < {db.timestamp_placeholder("delta")}
        )
        """,  # noqa: S608
        {"delta": delta},
    )


async def get_account_by_username(
    username: str, conn: Connection | None = None
) -> Account | None:
    if len(username) == 0:
        return None
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE LOWER(username) = :username",
        {"username": username.lower()},
        Account,
    )


async def get_account_by_pubkey(
    pubkey: str, conn: Connection | None = None
) -> Account | None:
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE LOWER(pubkey) = :pubkey",
        {"pubkey": pubkey.lower()},
        Account,
    )


async def get_account_by_email(
    email: str, conn: Connection | None = None
) -> Account | None:
    if len(email) == 0:
        return None
    return await (conn or db).fetchone(
        "SELECT * FROM accounts WHERE LOWER(email) = :email",
        {"email": email.lower()},
        Account,
    )


async def get_account_by_username_or_email(
    username_or_email: str, conn: Connection | None = None
) -> Account | None:
    return await (conn or db).fetchone(
        """
            SELECT * FROM accounts
            WHERE LOWER(email) = :value or LOWER(username) = :value
        """,
        {"value": username_or_email.lower()},
        Account,
    )


async def get_user(user_id: str, conn: Connection | None = None) -> User | None:
    account = await get_account(user_id, conn)
    if not account:
        return None
    return await get_user_from_account(account, conn)


async def get_user_from_account(
    account: Account, conn: Connection | None = None
) -> User | None:
    extensions = await get_user_active_extensions_ids(account.id, conn=conn)
    wallets = await get_wallets(account.id, deleted=False, conn=conn)

    if len(wallets) == 0:
        wallet = await create_wallet(user_id=account.id, conn=conn)
        wallets.append(wallet)

    return User(
        id=account.id,
        email=account.email,
        username=account.username,
        pubkey=account.pubkey,
        external_id=account.external_id,
        extra=account.extra,
        created_at=account.created_at,
        updated_at=account.updated_at,
        extensions=extensions,
        wallets=wallets,
        admin=account.is_admin,
        super_user=account.is_super_user,
        fiat_providers=account.fiat_providers,
        has_password=account.password_hash is not None,
    )


async def update_user_access_control_list(user_acls: UserAcls):
    user_acls.updated_at = datetime.now(timezone.utc)
    await db.update("accounts", user_acls)


async def get_user_access_control_lists(
    user_id: str, conn: Connection | None = None
) -> UserAcls:
    user_acls = await (conn or db).fetchone(
        "SELECT id, access_control_list FROM accounts WHERE id = :id",
        {"id": user_id},
        UserAcls,
    )

    return user_acls or UserAcls(id=user_id)
