import datetime
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

import shortuuid

from lnbits import bolt11
from lnbits.db import COCKROACH, POSTGRES, Connection, Filters
from lnbits.extension_manager import InstallableExtension
from lnbits.settings import AdminSettings, EditableSettings, SuperSettings, settings

from . import db
from .models import BalanceCheck, Payment, TinyURL, User, Wallet

# accounts
# --------


async def create_account(conn: Optional[Connection] = None) -> User:
    user_id = uuid4().hex
    await (conn or db).execute("INSERT INTO accounts (id) VALUES (?)", (user_id,))

    new_account = await get_account(user_id=user_id, conn=conn)
    assert new_account, "Newly created account couldn't be retrieved"

    return new_account


async def get_account(
    user_id: str, conn: Optional[Connection] = None
) -> Optional[User]:
    row = await (conn or db).fetchone(
        "SELECT id, email, pass as password FROM accounts WHERE id = ?", (user_id,)
    )

    return User(**row) if row else None


async def get_user(user_id: str, conn: Optional[Connection] = None) -> Optional[User]:
    user = await (conn or db).fetchone(
        "SELECT id, email FROM accounts WHERE id = ?", (user_id,)
    )

    if user:
        extensions = await (conn or db).fetchall(
            """SELECT extension FROM extensions WHERE "user" = ? AND active""",
            (user_id,),
        )
        wallets = await (conn or db).fetchall(
            """
            SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) AS balance_msat
            FROM wallets
            WHERE "user" = ?
            """,
            (user_id,),
        )
    else:
        return None

    return User(
        id=user["id"],
        email=user["email"],
        extensions=[e[0] for e in extensions],
        wallets=[Wallet(**w) for w in wallets],
        admin=user["id"] == settings.super_user
        or user["id"] in settings.lnbits_admin_users,
    )


# extensions
# -------


async def add_installed_extension(
    ext: InstallableExtension,
    conn: Optional[Connection] = None,
) -> None:
    meta = {
        "installed_release": dict(ext.installed_release)
        if ext.installed_release
        else None,
        "dependencies": ext.dependencies,
    }

    version = ext.installed_release.version if ext.installed_release else ""

    await (conn or db).execute(
        """
        INSERT INTO installed_extensions (id, version, name, short_description, icon, stars, meta) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO
        UPDATE SET (version, name, active, short_description, icon, stars, meta) = (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ext.id,
            version,
            ext.name,
            ext.short_description,
            ext.icon,
            ext.stars,
            json.dumps(meta),
            version,
            ext.name,
            False,
            ext.short_description,
            ext.icon,
            ext.stars,
            json.dumps(meta),
        ),
    )


async def update_installed_extension_state(
    *, ext_id: str, active: bool, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        UPDATE installed_extensions SET active = ? WHERE id = ?
        """,
        (active, ext_id),
    )


async def delete_installed_extension(
    *, ext_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        DELETE from installed_extensions  WHERE id = ?
        """,
        (ext_id,),
    )


async def get_installed_extension(ext_id: str, conn: Optional[Connection] = None):
    row = await (conn or db).fetchone(
        "SELECT * FROM installed_extensions WHERE id = ?",
        (ext_id,),
    )

    return dict(row) if row else None


async def get_installed_extensions(
    conn: Optional[Connection] = None,
) -> List["InstallableExtension"]:
    rows = await (conn or db).fetchall(
        "SELECT * FROM installed_extensions",
        (),
    )
    return [InstallableExtension.from_row(row) for row in rows]


async def get_inactive_extensions(*, conn: Optional[Connection] = None) -> List[str]:
    inactive_extensions = await (conn or db).fetchall(
        """SELECT id FROM installed_extensions WHERE NOT active""",
        (),
    )
    return [ext[0] for ext in inactive_extensions]


async def update_user_extension(
    *, user_id: str, extension: str, active: bool, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        INSERT INTO extensions ("user", extension, active) VALUES (?, ?, ?)
        ON CONFLICT ("user", extension) DO UPDATE SET active = ?
        """,
        (user_id, extension, active, active),
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
    await (conn or db).execute(
        """
        INSERT INTO wallets (id, name, "user", adminkey, inkey)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            wallet_id,
            wallet_name or settings.lnbits_default_wallet_name,
            user_id,
            uuid4().hex,
            uuid4().hex,
        ),
    )

    new_wallet = await get_wallet(wallet_id=wallet_id, conn=conn)
    assert new_wallet, "Newly created wallet couldn't be retrieved"

    return new_wallet


async def update_wallet(
    wallet_id: str, new_name: str, conn: Optional[Connection] = None
) -> Optional[Wallet]:
    return await (conn or db).execute(
        """
        UPDATE wallets SET
            name = ?
        WHERE id = ?
        """,
        (new_name, wallet_id),
    )


async def delete_wallet(
    *, user_id: str, wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        UPDATE wallets AS w
        SET
            "user" = 'del:' || w."user",
            adminkey = 'del:' || w.adminkey,
            inkey = 'del:' || w.inkey
        WHERE id = ? AND "user" = ?
        """,
        (wallet_id, user_id),
    )


async def get_wallet(
    wallet_id: str, conn: Optional[Connection] = None
) -> Optional[Wallet]:
    row = await (conn or db).fetchone(
        """
        SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) AS balance_msat
        FROM wallets
        WHERE id = ?
        """,
        (wallet_id,),
    )

    return Wallet(**row) if row else None


async def get_wallet_for_key(
    key: str, key_type: str = "invoice", conn: Optional[Connection] = None
) -> Optional[Wallet]:
    row = await (conn or db).fetchone(
        """
        SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) AS balance_msat
        FROM wallets
        WHERE adminkey = ? OR inkey = ?
        """,
        (key, key),
    )

    if not row:
        return None

    if key_type == "admin" and row["adminkey"] != key:
        return None

    return Wallet(**row)


async def get_total_balance(conn: Optional[Connection] = None):
    row = await (conn or db).fetchone("SELECT SUM(balance) FROM balances")
    return 0 if row[0] is None else row[0]


# wallet payments
# ---------------


async def get_standalone_payment(
    checking_id_or_hash: str,
    conn: Optional[Connection] = None,
    incoming: Optional[bool] = False,
    wallet_id: Optional[str] = None,
) -> Optional[Payment]:
    clause: str = "checking_id = ? OR hash = ?"
    values = [checking_id_or_hash, checking_id_or_hash]
    if incoming:
        clause = f"({clause}) AND amount > 0"

    if wallet_id:
        clause = f"({clause}) AND wallet = ?"
        values.append(wallet_id)

    row = await (conn or db).fetchone(
        f"""
        SELECT *
        FROM apipayments
        WHERE {clause}
        LIMIT 1
        """,
        tuple(values),
    )

    return Payment.from_row(row) if row else None


async def get_wallet_payment(
    wallet_id: str, payment_hash: str, conn: Optional[Connection] = None
) -> Optional[Payment]:
    row = await (conn or db).fetchone(
        """
        SELECT *
        FROM apipayments
        WHERE wallet = ? AND hash = ?
        """,
        (wallet_id, payment_hash),
    )

    return Payment.from_row(row) if row else None


async def get_latest_payments_by_extension(ext_name: str, ext_id: str, limit: int = 5):
    rows = await db.fetchall(
        f"""
        SELECT * FROM apipayments
        WHERE pending = 'false'
        AND extra LIKE ?
        AND extra LIKE ?
        ORDER BY time DESC LIMIT {limit}
        """,
        (
            f"%{ext_name}%",
            f"%{ext_id}%",
        ),
    )

    return rows


async def get_payments(
    *,
    wallet_id: Optional[str] = None,
    complete: bool = False,
    pending: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    since: Optional[int] = None,
    exclude_uncheckable: bool = False,
    filters: Optional[Filters[Payment]] = None,
    conn: Optional[Connection] = None,
) -> List[Payment]:
    """
    Filters payments to be returned by complete | pending | outgoing | incoming.
    """

    args: List[Any] = []
    clause: List[str] = []

    if since is not None:
        if db.type == POSTGRES:
            clause.append("time > to_timestamp(?)")
        elif db.type == COCKROACH:
            clause.append("time > cast(? AS timestamp)")
        else:
            clause.append("time > ?")
        args.append(since)

    if wallet_id:
        clause.append("wallet = ?")
        args.append(wallet_id)

    if complete and pending:
        pass
    elif complete:
        clause.append("((amount > 0 AND pending = false) OR amount < 0)")
    elif pending:
        clause.append("pending = true")
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

    if not filters:
        filters = Filters()

    rows = await (conn or db).fetchall(
        f"""
        SELECT *
        FROM apipayments
        {filters.where(clause)}
        ORDER BY time DESC
        {filters.pagination()}
        """,
        filters.values(args),
    )

    return [Payment.from_row(row) for row in rows]


async def delete_expired_invoices(
    conn: Optional[Connection] = None,
) -> None:
    # first we delete all invoices older than one month
    await (conn or db).execute(
        f"""
        DELETE FROM apipayments
        WHERE pending = true AND amount > 0
          AND time < {db.timestamp_now} - {db.interval_seconds(2592000)}
        """
    )
    # then we delete all invoices whose expiry date is in the past
    await (conn or db).execute(
        f"""
        DELETE FROM apipayments
        WHERE pending = true AND amount > 0
          AND expiry < {db.timestamp_now}
        """
    )


# payments
# --------


async def create_payment(
    *,
    wallet_id: str,
    checking_id: str,
    payment_request: str,
    payment_hash: str,
    amount: int,
    memo: str,
    fee: int = 0,
    preimage: Optional[str] = None,
    pending: bool = True,
    extra: Optional[Dict] = None,
    webhook: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> Payment:

    # todo: add this when tests are fixed
    # previous_payment = await get_wallet_payment(wallet_id, payment_hash, conn=conn)
    # assert previous_payment is None, "Payment already exists"

    try:
        invoice = bolt11.decode(payment_request)
        expiration_date = datetime.datetime.fromtimestamp(invoice.date + invoice.expiry)
    except:
        # assume maximum bolt11 expiry of 31 days to be on the safe side
        expiration_date = datetime.datetime.now() + datetime.timedelta(days=31)

    await (conn or db).execute(
        """
        INSERT INTO apipayments
          (wallet, checking_id, bolt11, hash, preimage,
           amount, pending, memo, fee, extra, webhook, expiry)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wallet_id,
            checking_id,
            payment_request,
            payment_hash,
            preimage,
            amount,
            pending,
            memo,
            fee,
            json.dumps(extra)
            if extra and extra != {} and type(extra) is dict
            else None,
            webhook,
            db.datetime_to_timestamp(expiration_date),
        ),
    )

    new_payment = await get_wallet_payment(wallet_id, payment_hash, conn=conn)
    assert new_payment, "Newly created payment couldn't be retrieved"

    return new_payment


async def update_payment_status(
    checking_id: str, pending: bool, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "UPDATE apipayments SET pending = ? WHERE checking_id = ?",
        (pending, checking_id),
    )


async def update_payment_details(
    checking_id: str,
    pending: Optional[bool] = None,
    fee: Optional[int] = None,
    preimage: Optional[str] = None,
    new_checking_id: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> None:

    set_clause: List[str] = []
    set_variables: List[Any] = []

    if new_checking_id is not None:
        set_clause.append("checking_id = ?")
        set_variables.append(new_checking_id)
    if pending is not None:
        set_clause.append("pending = ?")
        set_variables.append(pending)
    if fee is not None:
        set_clause.append("fee = ?")
        set_variables.append(fee)
    if preimage is not None:
        set_clause.append("preimage = ?")
        set_variables.append(preimage)

    set_variables.append(checking_id)

    await (conn or db).execute(
        f"UPDATE apipayments SET {', '.join(set_clause)} WHERE checking_id = ?",
        tuple(set_variables),
    )
    return


async def update_payment_extra(
    payment_hash: str,
    extra: dict,
    outgoing: bool = False,
    conn: Optional[Connection] = None,
) -> None:
    """
    Only update the `extra` field for the payment.
    Old values in the `extra` JSON object will be kept unless the new `extra` overwrites them.
    """

    amount_clause = "AND amount < 0" if outgoing else "AND amount > 0"

    row = await (conn or db).fetchone(
        f"SELECT hash, extra from apipayments WHERE hash = ? {amount_clause}",
        (payment_hash,),
    )
    if not row:
        return
    db_extra = json.loads(row["extra"] if row["extra"] else "{}")
    db_extra.update(extra)

    await (conn or db).execute(
        f"UPDATE apipayments SET extra = ? WHERE hash = ? {amount_clause} ",
        (json.dumps(db_extra), payment_hash),
    )


async def delete_payment(checking_id: str, conn: Optional[Connection] = None) -> None:
    await (conn or db).execute(
        "DELETE FROM apipayments WHERE checking_id = ?", (checking_id,)
    )


async def delete_wallet_payment(
    checking_id: str, wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "DELETE FROM apipayments WHERE checking_id = ? AND wallet = ?",
        (checking_id, wallet_id),
    )


async def check_internal(
    payment_hash: str, conn: Optional[Connection] = None
) -> Optional[str]:
    row = await (conn or db).fetchone(
        """
        SELECT checking_id FROM apipayments
        WHERE hash = ? AND pending AND amount > 0
        """,
        (payment_hash,),
    )
    if not row:
        return None
    else:
        return row["checking_id"]


# balance_check
# -------------


async def save_balance_check(
    wallet_id: str, url: str, conn: Optional[Connection] = None
):
    domain = urlparse(url).netloc

    await (conn or db).execute(
        """
        INSERT INTO balance_check (wallet, service, url) VALUES (?, ?, ?)
        ON CONFLICT (wallet, service) DO UPDATE SET url = ?
        """,
        (wallet_id, domain, url, url),
    )


async def get_balance_check(
    wallet_id: str, domain: str, conn: Optional[Connection] = None
) -> Optional[BalanceCheck]:
    row = await (conn or db).fetchone(
        """
        SELECT wallet, service, url
        FROM balance_check
        WHERE wallet = ? AND service = ?
        """,
        (wallet_id, domain),
    )
    return BalanceCheck.from_row(row) if row else None


async def get_balance_checks(conn: Optional[Connection] = None) -> List[BalanceCheck]:
    rows = await (conn or db).fetchall("SELECT wallet, service, url FROM balance_check")
    return [BalanceCheck.from_row(row) for row in rows]


# balance_notify
# --------------


async def save_balance_notify(
    wallet_id: str, url: str, conn: Optional[Connection] = None
):
    await (conn or db).execute(
        """
        INSERT INTO balance_notify (wallet, url) VALUES (?, ?)
        ON CONFLICT (wallet) DO UPDATE SET url = ?
        """,
        (wallet_id, url, url),
    )


async def get_balance_notify(
    wallet_id: str, conn: Optional[Connection] = None
) -> Optional[str]:
    row = await (conn or db).fetchone(
        """
        SELECT url
        FROM balance_notify
        WHERE wallet = ?
        """,
        (wallet_id,),
    )
    return row[0] if row else None


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
    admin_settings = AdminSettings(
        super_user=is_super_user,
        lnbits_allowed_funding_sources=settings.lnbits_allowed_funding_sources,
        **row_dict,
    )
    return admin_settings


async def delete_admin_settings():
    await db.execute("DELETE FROM settings")


async def update_admin_settings(data: EditableSettings):
    await db.execute("UPDATE settings SET editable_settings = ?", (json.dumps(data),))


async def update_super_user(super_user: str):
    await db.execute("UPDATE settings SET super_user = ?", (super_user,))
    return await get_super_settings()


async def create_admin_settings(super_user: str, new_settings: dict):
    sql = "INSERT INTO settings (super_user, editable_settings) VALUES (?, ?)"
    await db.execute(sql, (super_user, json.dumps(new_settings)))
    return await get_super_settings()


# db versions
# --------------
async def get_dbversions(conn: Optional[Connection] = None):
    rows = await (conn or db).fetchall("SELECT * FROM dbversions")
    return {row["db"]: row["version"] for row in rows}


async def update_migration_version(conn, db_name, version):
    await (conn or db).execute(
        """
        INSERT INTO dbversions (db, version) VALUES (?, ?)
        ON CONFLICT (db) DO UPDATE SET version = ?
        """,
        (db_name, version, version),
    )


# tinyurl
# -------


async def create_tinyurl(domain: str, endless: bool, wallet: str):
    tinyurl_id = shortuuid.uuid()[:8]
    await db.execute(
        "INSERT INTO tiny_url (id, url, endless, wallet) VALUES (?, ?, ?, ?)",
        (
            tinyurl_id,
            domain,
            endless,
            wallet,
        ),
    )
    return await get_tinyurl(tinyurl_id)


async def get_tinyurl(tinyurl_id: str) -> Optional[TinyURL]:
    row = await db.fetchone(
        "SELECT * FROM tiny_url WHERE id = ?",
        (tinyurl_id,),
    )
    return TinyURL.from_row(row) if row else None


async def get_tinyurl_by_url(url: str) -> List[TinyURL]:
    rows = await db.fetchall(
        "SELECT * FROM tiny_url WHERE url = ?",
        (url,),
    )
    return [TinyURL.from_row(row) for row in rows]


async def delete_tinyurl(tinyurl_id: str):
    await db.execute(
        "DELETE FROM tiny_url WHERE id = ?",
        (tinyurl_id,),
    )
