import json
from time import time
from typing import Literal, Optional
from uuid import uuid4

import shortuuid
from passlib.context import CryptContext

from lnbits.core.db import db
from lnbits.core.extensions.models import (
    InstallableExtension,
    PayToEnableInfo,
    UserExtension,
    UserExtensionInfo,
)
from lnbits.core.models import PaymentState
from lnbits.db import DB_TYPE, SQLITE, Connection, Database, Filters, Page
from lnbits.settings import (
    AdminSettings,
    EditableSettings,
    SuperSettings,
    settings,
)

from .models import (
    Account,
    AccountFilters,
    CreatePayment,
    Payment,
    PaymentFilters,
    PaymentHistoryPoint,
    TinyURL,
    UpdateUserPassword,
    UpdateUserPubkey,
    User,
    UserConfig,
    Wallet,
    WebPushSubscription,
)


async def create_account(
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    pubkey: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    user_config: Optional[UserConfig] = None,
    conn: Optional[Connection] = None,
) -> User:
    user_id = user_id or uuid4().hex
    extra = json.dumps(dict(user_config)) if user_config else "{}"
    now = int(time())
    now_ph = db.timestamp_placeholder("now")
    await (conn or db).execute(
        f"""
        INSERT INTO accounts
            (id, username, pass, email, pubkey, extra, created_at, updated_at)
        VALUES
            (:user, :username, :password, :email, :pubkey, :extra, {now_ph}, {now_ph})
        """,
        {
            "user": user_id,
            "username": username,
            "password": password,
            "email": email,
            "pubkey": pubkey,
            "extra": extra,
            "now": now,
        },
    )

    new_account = await get_account(user_id=user_id, conn=conn)
    assert new_account, "Newly created account couldn't be retrieved"

    return new_account


async def update_account(
    user_id: str,
    username: Optional[str] = None,
    email: Optional[str] = None,
    user_config: Optional[UserConfig] = None,
) -> Optional[User]:
    user = await get_account(user_id)
    assert user, "User not found"

    if email:
        assert not user.email or email == user.email, "Cannot change email."
        account = await get_account_by_email(email)
        assert not account or account.id == user_id, "Email already in use."

    if username:
        assert not user.username or username == user.username, "Cannot change username."
        account = await get_account_by_username(username)
        assert not account or account.id == user_id, "Username already exists."

    username = user.username or username
    email = user.email or email
    extra = user_config or user.config

    now = int(time())
    now_ph = db.timestamp_placeholder("now")
    await db.execute(
        f"""
            UPDATE accounts SET (username, email, extra, updated_at) =
            (:username, :email, :extra, {now_ph})
            WHERE id = :user
        """,
        {
            "username": username,
            "email": email,
            "extra": json.dumps(dict(extra)) if extra else "{}",
            "now": now,
            "user": user_id,
        },
    )

    user = await get_user(user_id)
    assert user, "Updated account couldn't be retrieved"
    return user


async def delete_account(user_id: str, conn: Optional[Connection] = None) -> None:
    await (conn or db).execute(
        "DELETE from accounts WHERE id = :user",
        {"user": user_id},
    )


async def get_accounts(
    filters: Optional[Filters[AccountFilters]] = None,
    conn: Optional[Connection] = None,
) -> Page[Account]:
    return await (conn or db).fetch_page(
        """
        SELECT
            accounts.id,
            accounts.username,
            accounts.email,
            SUM(COALESCE((
                SELECT balance FROM balances WHERE wallet = wallets.id
            ), 0)) as balance_msat,
            SUM((
                SELECT COUNT(*) FROM apipayments WHERE wallet = wallets.id
            )) as transaction_count,
            (
                SELECT COUNT(*) FROM wallets WHERE wallets.user = accounts.id
            ) as wallet_count,
            MAX((
                SELECT time FROM apipayments
                WHERE wallet = wallets.id ORDER BY time DESC LIMIT 1
            )) as last_payment
            FROM accounts LEFT JOIN wallets ON accounts.id = wallets.user
        """,
        [],
        {},
        filters=filters,
        model=Account,
        group_by=["accounts.id"],
    )


async def get_account(
    user_id: str, conn: Optional[Connection] = None
) -> Optional[User]:
    row = await (conn or db).fetchone(
        """
           SELECT id, email, username, pubkey, created_at, updated_at, extra
           FROM accounts WHERE id = :id
        """,
        {"id": user_id},
    )

    user = User(**row) if row else None
    if user and row["extra"]:
        user.config = UserConfig(**json.loads(row["extra"]))
    return user


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


async def get_user_password(user_id: str) -> Optional[str]:
    row = await db.fetchone(
        "SELECT pass FROM accounts WHERE id = :user",
        {"user": user_id},
    )
    return row.get("pass")


# TODO: refactor not a crud function
async def verify_user_password(user_id: str, password: str) -> bool:
    existing_password = await get_user_password(user_id)
    if not existing_password:
        return False

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(password, existing_password)


async def update_user_password(data: UpdateUserPassword, last_login_time: int) -> User:

    assert 0 <= time() - last_login_time <= settings.auth_credetials_update_threshold, (
        "You can only update your credentials in the first"
        f" {settings.auth_credetials_update_threshold} seconds."
        " Please login again or ask a new reset key!"
    )
    assert data.password == data.password_repeat, "Passwords do not match."

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    await db.execute(
        f"""
        UPDATE accounts
        SET pass = :pass, updated_at = {db.timestamp_placeholder("now")}
        WHERE id = :user
        """,
        {
            "pass": pwd_context.hash(data.password),
            "now": int(time()),
            "user": data.user_id,
        },
    )

    user = await get_user(data.user_id)
    assert user, "Updated account couldn't be retrieved."
    return user


async def update_user_pubkey(data: UpdateUserPubkey, last_login_time: int) -> User:

    assert 0 <= time() - last_login_time <= settings.auth_credetials_update_threshold, (
        "You can only update your credentials in the first"
        f" {settings.auth_credetials_update_threshold} seconds after login."
        " Please login again!"
    )

    user = await get_account_by_pubkey(data.pubkey)
    if user:
        assert user.id == data.user_id, "Public key already in use."

    await db.execute(
        f"""
        UPDATE accounts
        SET pubkey = :pubkey, updated_at = {db.timestamp_placeholder("now")}
        WHERE id = :user
        """,
        {
            "pubkey": data.pubkey,
            "now": int(time()),
            "user": data.user_id,
        },
    )

    user = await get_user(data.user_id)
    assert user, "Updated account couldn't be retrieved"
    return user


async def get_account_by_username(
    username: str, conn: Optional[Connection] = None
) -> Optional[User]:
    row = await (conn or db).fetchone(
        """
        SELECT id, username, pubkey, email, created_at, updated_at
        FROM accounts WHERE username = :username
        """,
        {"username": username},
    )

    return User(**row) if row else None


async def get_account_by_pubkey(
    pubkey: str, conn: Optional[Connection] = None
) -> Optional[User]:
    row = await (conn or db).fetchone(
        """
        SELECT id, username, pubkey, email, created_at, updated_at
        FROM accounts WHERE pubkey = :pubkey
        """,
        {"pubkey": pubkey},
    )

    return User(**row) if row else None


async def get_account_by_email(
    email: str, conn: Optional[Connection] = None
) -> Optional[User]:
    row = await (conn or db).fetchone(
        """
        SELECT id, username, pubkey, email, created_at, updated_at
        FROM accounts WHERE email = :email
        """,
        {"email": email},
    )

    return User(**row) if row else None


async def get_account_by_username_or_email(
    username_or_email: str, conn: Optional[Connection] = None
) -> Optional[User]:
    user = await get_account_by_username(username_or_email, conn)
    if not user:
        user = await get_account_by_email(username_or_email, conn)
    return user


async def get_user(user_id: str, conn: Optional[Connection] = None) -> Optional[User]:
    user = await (conn or db).fetchone(
        """
        SELECT id, email, username, pubkey, pass, extra, created_at, updated_at
        FROM accounts WHERE id = :id
        """,
        {"id": user_id},
    )

    if user:
        extensions = await get_user_active_extensions_ids(user_id, conn)
        wallets = await (conn or db).fetchall(
            """
            SELECT *, COALESCE((
                SELECT balance FROM balances WHERE wallet = wallets.id
            ), 0) AS balance_msat
            FROM wallets
            WHERE "user" = :user and wallets.deleted = false
            """,
            {"user": user_id},
        )
    else:
        return None

    return User(
        id=user["id"],
        email=user["email"],
        username=user["username"],
        pubkey=user["pubkey"],
        extensions=[
            e for e in extensions if User.is_extension_for_user(e[0], user["id"])
        ],
        wallets=[Wallet(**w) for w in wallets],
        admin=user["id"] == settings.super_user
        or user["id"] in settings.lnbits_admin_users,
        super_user=user["id"] == settings.super_user,
        has_password=True if user["pass"] else False,
        config=UserConfig(**json.loads(user["extra"])) if user["extra"] else None,
    )


# extensions
# -------


async def add_installed_extension(
    ext: InstallableExtension,
    conn: Optional[Connection] = None,
) -> None:
    meta = {
        "installed_release": (
            dict(ext.installed_release) if ext.installed_release else None
        ),
        "pay_to_enable": (dict(ext.pay_to_enable) if ext.pay_to_enable else None),
        "dependencies": ext.dependencies,
        "payments": [dict(p) for p in ext.payments] if ext.payments else None,
    }

    version = ext.installed_release.version if ext.installed_release else ""

    await (conn or db).execute(
        """
        INSERT INTO installed_extensions
        (id, version, name, active, short_description, icon, stars, meta)
        VALUES
        (:ext, :version, :name, :active, :short_description, :icon, :stars, :meta)
        ON CONFLICT (id) DO UPDATE SET
        (version, name, active, short_description, icon, stars, meta) =
        (:version, :name, :active, :short_description, :icon, :stars, :meta)
        """,
        {
            "ext": ext.id,
            "version": version,
            "name": ext.name,
            "active": ext.active,
            "short_description": ext.short_description,
            "icon": ext.icon,
            "stars": ext.stars,
            "meta": json.dumps(meta),
        },
    )


async def update_installed_extension_state(
    *, ext_id: str, active: bool, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        UPDATE installed_extensions SET active = :active WHERE id = :ext
        """,
        {"ext": ext_id, "active": active},
    )


async def update_extension_pay_to_enable(
    ext_id: str, payment_info: PayToEnableInfo, conn: Optional[Connection] = None
) -> None:
    ext = await get_installed_extension(ext_id, conn)
    if not ext:
        return
    ext.pay_to_enable = payment_info

    await add_installed_extension(ext, conn)


async def delete_installed_extension(
    *, ext_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        DELETE from installed_extensions  WHERE id = :ext
        """,
        {"ext": ext_id},
    )


async def drop_extension_db(*, ext_id: str, conn: Optional[Connection] = None) -> None:
    db_version = await (conn or db).fetchone(
        "SELECT * FROM dbversions WHERE db = :id",
        {"id": ext_id},
    )
    # Check that 'ext_id' is a valid extension id and not a malicious string
    assert db_version, f"Extension '{ext_id}' db version cannot be found"

    is_file_based_db = await Database.clean_ext_db_files(ext_id)
    if is_file_based_db:
        return

    # String formatting is required, params are not accepted for 'DROP SCHEMA'.
    # The `ext_id` value is verified above.
    await (conn or db).execute(
        f"DROP SCHEMA IF EXISTS {ext_id} CASCADE",
    )


async def get_installed_extension(
    ext_id: str, conn: Optional[Connection] = None
) -> Optional[InstallableExtension]:
    row = await (conn or db).fetchone(
        "SELECT * FROM installed_extensions WHERE id = :id",
        {"id": ext_id},
    )

    return InstallableExtension.from_row(row) if row else None


async def get_installed_extensions(
    active: Optional[bool] = None,
    conn: Optional[Connection] = None,
) -> list[InstallableExtension]:
    rows = await (conn or db).fetchall(
        "SELECT * FROM installed_extensions",
    )
    all_extensions = [InstallableExtension.from_row(row) for row in rows]
    if active is None:
        return all_extensions

    return [e for e in all_extensions if e.active == active]


async def get_user_extension(
    user_id: str, extension: str, conn: Optional[Connection] = None
) -> Optional[UserExtension]:
    row = await (conn or db).fetchone(
        """
            SELECT extension, active, extra as _extra FROM extensions
            WHERE "user" = :user AND extension = :ext
        """,
        {"user": user_id, "ext": extension},
    )
    return UserExtension.from_row(row) if row else None


async def get_user_extensions(
    user_id: str, conn: Optional[Connection] = None
) -> list[UserExtension]:
    rows = await (conn or db).fetchall(
        """
            SELECT extension, active, extra as _extra FROM extensions
            WHERE "user" = :user
        """,
        {"user": user_id},
    )
    return [UserExtension.from_row(row) for row in rows]


async def update_user_extension(
    *, user_id: str, extension: str, active: bool, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        INSERT INTO extensions ("user", extension, active) VALUES (:user, :ext, :active)
        ON CONFLICT ("user", extension) DO UPDATE SET active = :active
        """,
        {"user": user_id, "ext": extension, "active": active},
    )


async def get_user_active_extensions_ids(
    user_id: str, conn: Optional[Connection] = None
) -> list[str]:
    rows = await (conn or db).fetchall(
        """
        SELECT extension FROM extensions WHERE "user" = :user AND active
        """,
        {"user": user_id},
    )
    return [e.get("extension", "") for e in rows]


async def update_user_extension_extra(
    user_id: str,
    extension: str,
    extra: UserExtensionInfo,
    conn: Optional[Connection] = None,
) -> None:
    extra_json = json.dumps(dict(extra))
    await (conn or db).execute(
        """
        INSERT INTO extensions ("user", extension, extra) VALUES
        (:user, :ext, :extra)
        ON CONFLICT ("user", extension) DO UPDATE SET extra = :extra
        """,
        {"user": user_id, "ext": extension, "extra": extra_json},
    )


# wallets
# -------


async def create_wallet(
    *,
    user_id: str,
    wallet_name: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> Wallet:
    wallet_id = uuid4().hex
    now = int(time())
    now_ph = db.timestamp_placeholder("now")
    await (conn or db).execute(
        f"""
        INSERT INTO wallets (id, name, "user", adminkey, inkey, created_at, updated_at)
        VALUES (:wallet, :name, :user, :adminkey, :inkey, {now_ph}, {now_ph})
        """,
        {
            "wallet": wallet_id,
            "name": wallet_name or settings.lnbits_default_wallet_name,
            "user": user_id,
            "adminkey": uuid4().hex,
            "inkey": uuid4().hex,
            "now": now,
        },
    )

    new_wallet = await get_wallet(wallet_id=wallet_id, conn=conn)
    assert new_wallet, "Newly created wallet couldn't be retrieved"

    return new_wallet


async def update_wallet(
    wallet_id: str,
    name: Optional[str] = None,
    currency: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> Optional[Wallet]:
    set_clause = []
    set_clause.append(f"updated_at = {db.timestamp_placeholder('now')}")
    values: dict = {
        "wallet": wallet_id,
        "now": int(time()),
    }
    if name:
        set_clause.append("name = :name")
        values["name"] = name
    if currency is not None:
        set_clause.append("currency = :currency")
        values["currency"] = currency
    await (conn or db).execute(
        f"""
        UPDATE wallets SET {', '.join(set_clause)} WHERE id = :wallet
        """,
        values,
    )
    wallet = await get_wallet(wallet_id=wallet_id, conn=conn)
    assert wallet, "updated created wallet couldn't be retrieved"
    return wallet


async def delete_wallet(
    *,
    user_id: str,
    wallet_id: str,
    deleted: bool = True,
    conn: Optional[Connection] = None,
) -> None:
    now = int(time())
    await (conn or db).execute(
        f"""
        UPDATE wallets
        SET deleted = :deleted, updated_at = {db.timestamp_placeholder('now')}
        WHERE id = :wallet AND "user" = :user
        """,
        {"wallet": wallet_id, "user": user_id, "deleted": deleted, "now": now},
    )


async def force_delete_wallet(
    wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "DELETE FROM wallets WHERE id = :wallet",
        {"wallet": wallet_id},
    )


async def delete_wallet_by_id(
    *, wallet_id: str, conn: Optional[Connection] = None
) -> Optional[int]:
    now = int(time())
    result = await (conn or db).execute(
        f"""
        UPDATE wallets
        SET deleted = true, updated_at = {db.timestamp_placeholder('now')}
        WHERE id = :wallet
        """,
        {"wallet": wallet_id, "now": now},
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
            SELECT COUNT(*) FROM apipayments WHERE wallet = wallets.id
        ) = 0 AND (
            (updated_at is null AND created_at < :delta)
            OR updated_at < :delta
        )
        """,
        {"delta": delta},
    )


async def get_wallet(
    wallet_id: str, conn: Optional[Connection] = None
) -> Optional[Wallet]:
    row = await (conn or db).fetchone(
        """
        SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0)
        AS balance_msat FROM wallets WHERE id = :wallet
        """,
        {"wallet": wallet_id},
    )

    return Wallet(**row) if row else None


async def get_wallets(user_id: str, conn: Optional[Connection] = None) -> list[Wallet]:
    rows = await (conn or db).fetchall(
        """
        SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0)
        AS balance_msat FROM wallets WHERE "user" = :user
        """,
        {"user": user_id},
    )

    return [Wallet(**row) for row in rows]


async def get_wallet_for_key(
    key: str,
    conn: Optional[Connection] = None,
) -> Optional[Wallet]:
    row = await (conn or db).fetchone(
        """
        SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0)
        AS balance_msat FROM wallets
        WHERE (adminkey = :key OR inkey = :key) AND deleted = false
        """,
        {"key": key},
    )

    if not row:
        return None

    return Wallet(**row)


async def get_total_balance(conn: Optional[Connection] = None):
    row = await (conn or db).fetchone("SELECT SUM(balance) FROM balances")
    return row.get("balance", 0)


# wallet payments
# ---------------


async def get_standalone_payment(
    checking_id_or_hash: str,
    conn: Optional[Connection] = None,
    incoming: Optional[bool] = False,
    wallet_id: Optional[str] = None,
) -> Optional[Payment]:
    clause: str = "checking_id = :checking_id OR hash = :hash"
    values = {
        "wallet": wallet_id,
        "checking_id": checking_id_or_hash,
        "hash": checking_id_or_hash,
    }
    if incoming:
        clause = f"({clause}) AND amount > 0"

    if wallet_id:
        clause = f"({clause}) AND wallet = :wallet"

    row = await (conn or db).fetchone(
        f"""
        SELECT *
        FROM apipayments
        WHERE {clause}
        ORDER BY amount
        LIMIT 1
        """,
        values,
    )

    return Payment.from_row(row) if row else None


async def get_wallet_payment(
    wallet_id: str, payment_hash: str, conn: Optional[Connection] = None
) -> Optional[Payment]:
    row = await (conn or db).fetchone(
        """
        SELECT *
        FROM apipayments
        WHERE wallet = :wallet AND hash = :hash
        """,
        {"wallet": wallet_id, "hash": payment_hash},
    )

    return Payment.from_row(row) if row else None


async def get_latest_payments_by_extension(ext_name: str, ext_id: str, limit: int = 5):
    rows = await db.fetchall(
        f"""
        SELECT * FROM apipayments
        WHERE status = '{PaymentState.SUCCESS}'
        AND extra LIKE :ext_name
        AND extra LIKE :ext_id
        ORDER BY time DESC LIMIT {limit}
        """,
        {"ext_name": f"%{ext_name}%", "ext_id": f"%{ext_id}%"},
    )

    return rows


async def get_payments_paginated(
    *,
    wallet_id: Optional[str] = None,
    complete: bool = False,
    pending: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    since: Optional[int] = None,
    exclude_uncheckable: bool = False,
    filters: Optional[Filters[PaymentFilters]] = None,
    conn: Optional[Connection] = None,
) -> Page[Payment]:
    """
    Filters payments to be returned by complete | pending | outgoing | incoming.
    """

    values: dict = {
        "wallet": wallet_id,
        "time": since,
    }
    clause: list[str] = []

    if since is not None:
        clause.append(f"time > {db.timestamp_placeholder('time')}")

    if wallet_id:
        clause.append("wallet = :wallet")

    if complete and pending:
        pass
    elif complete:
        clause.append(
            f"((amount > 0 AND status = '{PaymentState.SUCCESS}') OR amount < 0)"
        )
    elif pending:
        clause.append(f"status = '{PaymentState.PENDING}'")
    else:
        pass

    if outgoing and incoming:
        pass
    elif outgoing:
        clause.append("amount < 0")
    elif incoming:
        clause.append("amount > 0")
    else:
        pass

    if exclude_uncheckable:  # checkable means it has a checking_id that isn't internal
        clause.append("checking_id NOT LIKE 'temp_%'")
        clause.append("checking_id NOT LIKE 'internal_%'")

    return await (conn or db).fetch_page(
        "SELECT * FROM apipayments",
        clause,
        values,
        filters=filters,
        model=Payment,
    )


async def get_payments(
    *,
    wallet_id: Optional[str] = None,
    complete: bool = False,
    pending: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    since: Optional[int] = None,
    exclude_uncheckable: bool = False,
    filters: Optional[Filters[PaymentFilters]] = None,
    conn: Optional[Connection] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[Payment]:
    """
    Filters payments to be returned by complete | pending | outgoing | incoming.
    """

    filters = filters or Filters()

    filters.sortby = filters.sortby or "time"
    filters.direction = filters.direction or "desc"
    filters.limit = limit or filters.limit
    filters.offset = offset or filters.offset

    page = await get_payments_paginated(
        wallet_id=wallet_id,
        complete=complete,
        pending=pending,
        outgoing=outgoing,
        incoming=incoming,
        since=since,
        exclude_uncheckable=exclude_uncheckable,
        filters=filters,
        conn=conn,
    )

    return page.data


async def delete_expired_invoices(
    conn: Optional[Connection] = None,
) -> None:
    # first we delete all invoices older than one month

    await (conn or db).execute(
        f"""
        DELETE FROM apipayments
        WHERE status = '{PaymentState.PENDING}' AND amount > 0
        AND time < {db.timestamp_placeholder("delta")}
        """,
        {"delta": int(time() - 2592000)},
    )
    # then we delete all invoices whose expiry date is in the past
    await (conn or db).execute(
        f"""
        DELETE FROM apipayments
        WHERE status = '{PaymentState.PENDING}' AND amount > 0
        AND expiry < {db.timestamp_placeholder("now")}
        """,
        {"now": int(time())},
    )


# payments
# --------


async def create_payment(
    checking_id: str,
    data: CreatePayment,
    status: PaymentState = PaymentState.PENDING,
    conn: Optional[Connection] = None,
) -> Payment:
    # we don't allow the creation of the same invoice twice
    # note: this can be removed if the db uniqueness constraints are set appropriately
    previous_payment = await get_standalone_payment(checking_id, conn=conn)
    assert previous_payment is None, "Payment already exists"

    expiry_ph = db.timestamp_placeholder("expiry")
    await (conn or db).execute(
        f"""
        INSERT INTO apipayments
          (wallet, checking_id, bolt11, hash, preimage,
           amount, status, memo, fee, extra, webhook, expiry, pending)
          VALUES (:wallet, :checking_id, :bolt11, :hash, :preimage,
           :amount, :status, :memo, :fee, :extra, :webhook, {expiry_ph}, :pending)
        """,
        {
            "wallet": data.wallet_id,
            "checking_id": checking_id,
            "bolt11": data.payment_request,
            "hash": data.payment_hash,
            "preimage": data.preimage,
            "amount": data.amount,
            "status": status.value,
            "memo": data.memo,
            "fee": data.fee,
            "extra": (
                json.dumps(data.extra)
                if data.extra and data.extra != {} and isinstance(data.extra, dict)
                else None
            ),
            "webhook": data.webhook,
            "expiry": data.expiry if data.expiry else None,
            "pending": False,  # TODO: remove this in next release
        },
    )

    new_payment = await get_wallet_payment(data.wallet_id, data.payment_hash, conn=conn)
    assert new_payment, "Newly created payment couldn't be retrieved"

    return new_payment


async def update_payment_status(
    checking_id: str, status: PaymentState, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "UPDATE apipayments SET status = :status WHERE checking_id = :checking_id",
        {"status": status.value, "checking_id": checking_id},
    )


async def update_payment_details(
    checking_id: str,
    status: Optional[PaymentState] = None,
    fee: Optional[int] = None,
    preimage: Optional[str] = None,
    new_checking_id: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> None:
    set_variables: dict = {
        "checking_id": checking_id,
        "new_checking_id": new_checking_id,
        "status": status.value if status else None,
        "fee": fee,
        "preimage": preimage,
    }

    set_clause: list[str] = []
    if new_checking_id is not None:
        set_clause.append("checking_id = :new_checking_id")
    if status is not None:
        set_clause.append("status = :status")
    if fee is not None:
        set_clause.append("fee = :fee")
    if preimage is not None:
        set_clause.append("preimage = :preimage")

    await (conn or db).execute(
        f"""
        UPDATE apipayments SET {', '.join(set_clause)}
        WHERE checking_id = :checking_id
        """,
        set_variables,
    )


async def update_payment_extra(
    payment_hash: str,
    extra: dict,
    outgoing: bool = False,
    conn: Optional[Connection] = None,
) -> None:
    """
    Only update the `extra` field for the payment.
    Old values in the `extra` JSON object will be kept
    unless the new `extra` overwrites them.
    """

    amount_clause = "AND amount < 0" if outgoing else "AND amount > 0"

    row = await (conn or db).fetchone(
        f"SELECT hash, extra from apipayments WHERE hash = :hash {amount_clause}",
        {"hash": payment_hash},
    )
    if not row:
        return
    db_extra = json.loads(row["extra"] if row["extra"] else "{}")
    db_extra.update(extra)

    await (conn or db).execute(
        f"UPDATE apipayments SET extra = :extra WHERE hash = :hash {amount_clause} ",
        {"extra": json.dumps(db_extra), "hash": payment_hash},
    )


DateTrunc = Literal["hour", "day", "month"]
sqlite_formats = {
    "hour": "%Y-%m-%d %H:00:00",
    "day": "%Y-%m-%d 00:00:00",
    "month": "%Y-%m-01 00:00:00",
}


async def get_payments_history(
    wallet_id: Optional[str] = None,
    group: DateTrunc = "day",
    filters: Optional[Filters] = None,
) -> list[PaymentHistoryPoint]:
    if not filters:
        filters = Filters()

    if DB_TYPE == SQLITE and group in sqlite_formats:
        date_trunc = f"strftime('{sqlite_formats[group]}', time, 'unixepoch')"
    elif group in ("day", "hour", "month"):
        date_trunc = f"date_trunc('{group}', time)"
    else:
        raise ValueError(f"Invalid group value: {group}")

    values = {
        "wallet": wallet_id,
    }
    where = [f"wallet = :wallet AND (status = '{PaymentState.SUCCESS}' OR amount < 0)"]
    transactions = await db.fetchall(
        f"""
        SELECT {date_trunc} date,
               SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) income,
               SUM(CASE WHEN amount < 0 THEN abs(amount) + abs(fee) ELSE 0 END) spending
        FROM apipayments
        {filters.where(where)}
        GROUP BY date
        ORDER BY date DESC
        """,
        filters.values(values),
    )
    if wallet_id:
        wallet = await get_wallet(wallet_id)
        if wallet:
            balance = wallet.balance_msat
        else:
            raise ValueError("Unknown wallet")
    else:
        balance = await get_total_balance()

    # since we dont know the balance at the starting point,
    # we take the current balance and walk backwards
    results: list[PaymentHistoryPoint] = []
    for row in transactions:
        results.insert(
            0,
            PaymentHistoryPoint(
                balance=balance,
                date=row.get("date", 0),
                income=row.get("income", 0),
                spending=row.get("spending", 0),
            ),
        )
        balance -= row.get("income", 0) - row.get("spending", 0)
    return results


async def delete_wallet_payment(
    checking_id: str, wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "DELETE FROM apipayments WHERE checking_id = :checking_id AND wallet = :wallet",
        {"checking_id": checking_id, "wallet": wallet_id},
    )


async def check_internal(
    payment_hash: str, conn: Optional[Connection] = None
) -> Optional[str]:
    """
    Returns the checking_id of the internal payment if it exists,
    otherwise None
    """
    row = await (conn or db).fetchone(
        f"""
        SELECT checking_id FROM apipayments
        WHERE hash = :hash AND status = '{PaymentState.PENDING}' AND amount > 0
        """,
        {"hash": payment_hash},
    )
    if not row:
        return None
    else:
        return row["checking_id"]


async def check_internal_pending(
    payment_hash: str, conn: Optional[Connection] = None
) -> bool:
    """
    Returns False if the internal payment is not pending anymore
    (and thus paid), otherwise True
    """
    row = await (conn or db).fetchone(
        """
        SELECT status FROM apipayments
        WHERE hash = :hash AND amount > 0
        """,
        {"hash": payment_hash},
    )
    if not row:
        return True
    return row["status"] == PaymentState.PENDING.value


async def mark_webhook_sent(payment_hash: str, status: int) -> None:
    await db.execute(
        """
        UPDATE apipayments SET webhook_status = :status
        WHERE hash = :hash
        """,
        {"status": status, "hash": payment_hash},
    )


# admin
# --------


async def get_super_settings() -> Optional[SuperSettings]:
    row = await db.fetchone("SELECT * FROM settings")
    if not row:
        return None
    editable_settings = json.loads(row["editable_settings"])
    return SuperSettings(**{"super_user": row["super_user"], **editable_settings})


async def get_admin_settings(is_super_user: bool = False) -> Optional[AdminSettings]:
    sets = await get_super_settings()
    if not sets:
        return None
    row_dict = dict(sets)
    row_dict.pop("super_user")
    row_dict.pop("auth_all_methods")

    admin_settings = AdminSettings(
        is_super_user=is_super_user,
        lnbits_allowed_funding_sources=settings.lnbits_allowed_funding_sources,
        **row_dict,
    )
    return admin_settings


async def delete_admin_settings() -> None:
    await db.execute("DELETE FROM settings")


async def update_admin_settings(data: EditableSettings) -> None:
    row = await db.fetchone("SELECT editable_settings FROM settings")
    editable_settings = json.loads(row["editable_settings"]) if row else {}
    editable_settings.update(data.dict(exclude_unset=True))
    await db.execute(
        "UPDATE settings SET editable_settings = :settings",
        {"settings": json.dumps(editable_settings)},
    )


async def update_super_user(super_user: str) -> SuperSettings:
    await db.execute(
        "UPDATE settings SET super_user = :user",
        {"user": super_user},
    )
    settings = await get_super_settings()
    assert settings, "updated super_user settings could not be retrieved"
    return settings


async def create_admin_settings(super_user: str, new_settings: dict):
    await db.execute(
        """
        INSERT INTO settings (super_user, editable_settings)
        VALUES (:user, :settings)
        """,
        {"user": super_user, "settings": json.dumps(new_settings)},
    )
    settings = await get_super_settings()
    assert settings, "created admin settings could not be retrieved"
    return settings


# db versions
# --------------
async def get_dbversions(conn: Optional[Connection] = None):
    rows = await (conn or db).fetchall("SELECT * FROM dbversions")
    return {row["db"]: row["version"] for row in rows}


async def update_migration_version(conn, db_name, version):
    await (conn or db).execute(
        """
        INSERT INTO dbversions (db, version) VALUES (:db, :version)
        ON CONFLICT (db) DO UPDATE SET version = :version
        """,
        {"db": db_name, "version": version},
    )


async def delete_dbversion(*, ext_id: str, conn: Optional[Connection] = None) -> None:
    await (conn or db).execute(
        """
        DELETE FROM dbversions WHERE db = :ext
        """,
        {"ext": ext_id},
    )


# tinyurl
# -------


async def create_tinyurl(domain: str, endless: bool, wallet: str):
    tinyurl_id = shortuuid.uuid()[:8]
    await db.execute(
        """
        INSERT INTO tiny_url (id, url, endless, wallet)
        VALUES (:tinyurl, :domain, :endless, :wallet)
        """,
        {"tinyurl": tinyurl_id, "domain": domain, "endless": endless, "wallet": wallet},
    )
    return await get_tinyurl(tinyurl_id)


async def get_tinyurl(tinyurl_id: str) -> Optional[TinyURL]:
    row = await db.fetchone(
        "SELECT * FROM tiny_url WHERE id = :tinyurl",
        {"tinyurl": tinyurl_id},
    )
    return TinyURL.from_row(row) if row else None


async def get_tinyurl_by_url(url: str) -> list[TinyURL]:
    rows = await db.fetchall(
        "SELECT * FROM tiny_url WHERE url = :url",
        {"url": url},
    )
    return [TinyURL.from_row(row) for row in rows]


async def delete_tinyurl(tinyurl_id: str):
    await db.execute(
        "DELETE FROM tiny_url WHERE id = :tinyurl",
        {"tinyurl": tinyurl_id},
    )


# push_notification
# -----------------


async def get_webpush_subscription(
    endpoint: str, user: str
) -> Optional[WebPushSubscription]:
    row = await db.fetchone(
        """
        SELECT * FROM webpush_subscriptions
        WHERE endpoint = :endpoint AND "user" = :user
        """,
        {"endpoint": endpoint, "user": user},
    )
    return WebPushSubscription(**dict(row)) if row else None


async def get_webpush_subscriptions_for_user(
    user: str,
) -> list[WebPushSubscription]:
    rows = await db.fetchall(
        """SELECT * FROM webpush_subscriptions WHERE "user" = :user""",
        {"user": user},
    )
    return [WebPushSubscription(**dict(row)) for row in rows]


async def create_webpush_subscription(
    endpoint: str, user: str, data: str, host: str
) -> WebPushSubscription:
    await db.execute(
        """
        INSERT INTO webpush_subscriptions (endpoint, "user", data, host)
        VALUES (:endpoint, :user, :data, :host)
        """,
        {"endpoint": endpoint, "user": user, "data": data, "host": host},
    )
    subscription = await get_webpush_subscription(endpoint, user)
    assert subscription, "Newly created webpush subscription couldn't be retrieved"
    return subscription


async def delete_webpush_subscription(endpoint: str, user: str) -> int:
    resp = await db.execute(
        """
        DELETE FROM webpush_subscriptions WHERE endpoint = :endpoint AND "user" = :user
        """,
        {"endpoint": endpoint, "user": user},
    )
    return resp.rowcount


async def delete_webpush_subscriptions(endpoint: str) -> int:
    resp = await db.execute(
        "DELETE FROM webpush_subscriptions WHERE endpoint = :endpoint",
        {"endpoint": endpoint},
    )
    return resp.rowcount
