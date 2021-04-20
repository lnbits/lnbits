import json
import datetime
from uuid import uuid4
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from lnbits import bolt11
from lnbits.db import Connection
from lnbits.settings import DEFAULT_WALLET_NAME

from . import db
from .models import User, Wallet, Payment, BalanceCheck


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
            "SELECT extension FROM extensions WHERE user = ? AND active = 1", (user_id,)
        )
        wallets = await (conn or db).fetchall(
            """
            SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) AS balance_msat
            FROM wallets
            WHERE user = ?
            """,
            (user_id,),
        )

    return (
        User(
            **{
                **user,
                **{
                    "extensions": [e[0] for e in extensions],
                    "wallets": [Wallet(**w) for w in wallets],
                },
            }
        )
        if user
        else None
    )


async def update_user_extension(
    *, user_id: str, extension: str, active: int, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        INSERT OR REPLACE INTO extensions (user, extension, active)
        VALUES (?, ?, ?)
        """,
        (user_id, extension, active),
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
        INSERT INTO wallets (id, name, user, adminkey, inkey)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            wallet_id,
            wallet_name or DEFAULT_WALLET_NAME,
            user_id,
            uuid4().hex,
            uuid4().hex,
        ),
    )

    new_wallet = await get_wallet(wallet_id=wallet_id, conn=conn)
    assert new_wallet, "Newly created wallet couldn't be retrieved"

    return new_wallet


async def delete_wallet(
    *, user_id: str, wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        """
        UPDATE wallets AS w
        SET
            user = 'del:' || w.user,
            adminkey = 'del:' || w.adminkey,
            inkey = 'del:' || w.inkey
        WHERE id = ? AND user = ?
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


# wallet payments
# ---------------


async def get_standalone_payment(
    checking_id_or_hash: str, conn: Optional[Connection] = None
) -> Optional[Payment]:
    row = await (conn or db).fetchone(
        """
        SELECT *
        FROM apipayments
        WHERE checking_id = ? OR hash = ?
        LIMIT 1
        """,
        (checking_id_or_hash, checking_id_or_hash),
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


async def get_payments(
    *,
    wallet_id: Optional[str] = None,
    complete: bool = False,
    pending: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    since: Optional[int] = None,
    exclude_uncheckable: bool = False,
    conn: Optional[Connection] = None,
) -> List[Payment]:
    """
    Filters payments to be returned by complete | pending | outgoing | incoming.
    """

    args: List[Any] = []
    clause: List[str] = []

    if since != None:
        clause.append("time > ?")
        args.append(since)

    if wallet_id:
        clause.append("wallet = ?")
        args.append(wallet_id)

    if complete and pending:
        pass
    elif complete:
        clause.append("((amount > 0 AND pending = 0) OR amount < 0)")
    elif pending:
        clause.append("pending = 1")
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

    where = ""
    if clause:
        where = f"WHERE {' AND '.join(clause)}"

    rows = await (conn or db).fetchall(
        f"""
        SELECT *
        FROM apipayments
        {where}
        ORDER BY time DESC
        """,
        tuple(args),
    )

    return [Payment.from_row(row) for row in rows]


async def delete_expired_invoices(
    conn: Optional[Connection] = None,
) -> None:
    rows = await (conn or db).fetchall(
        """
        SELECT bolt11
        FROM apipayments
        WHERE pending = 1 AND amount > 0 AND time < strftime('%s', 'now') - 86400
    """
    )
    for (payment_request,) in rows:
        try:
            invoice = bolt11.decode(payment_request)
        except:
            continue

        expiration_date = datetime.datetime.fromtimestamp(invoice.date + invoice.expiry)
        if expiration_date > datetime.datetime.utcnow():
            continue

        await (conn or db).execute(
            """
            DELETE FROM apipayments
            WHERE pending = 1 AND hash = ?
            """,
            (invoice.payment_hash,),
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
    await (conn or db).execute(
        """
        INSERT INTO apipayments
          (wallet, checking_id, bolt11, hash, preimage,
           amount, pending, memo, fee, extra, webhook)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wallet_id,
            checking_id,
            payment_request,
            payment_hash,
            preimage,
            amount,
            int(pending),
            memo,
            fee,
            json.dumps(extra)
            if extra and extra != {} and type(extra) is dict
            else None,
            webhook,
        ),
    )

    new_payment = await get_wallet_payment(wallet_id, payment_hash, conn=conn)
    assert new_payment, "Newly created payment couldn't be retrieved"

    return new_payment


async def update_payment_status(
    checking_id: str,
    pending: bool,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).execute(
        "UPDATE apipayments SET pending = ? WHERE checking_id = ?",
        (
            int(pending),
            checking_id,
        ),
    )


async def delete_payment(
    checking_id: str,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).execute(
        "DELETE FROM apipayments WHERE checking_id = ?", (checking_id,)
    )


async def check_internal(
    payment_hash: str,
    conn: Optional[Connection] = None,
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
    wallet_id: str,
    url: str,
    conn: Optional[Connection] = None,
):
    domain = urlparse(url).netloc

    await (conn or db).execute(
        """
        INSERT OR REPLACE INTO balance_check (wallet, service, url)
        VALUES (?, ?, ?)
        """,
        (wallet_id, domain, url),
    )


async def get_balance_check(
    wallet_id: str,
    domain: str,
    conn: Optional[Connection] = None,
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
    wallet_id: str,
    url: str,
    conn: Optional[Connection] = None,
):
    await (conn or db).execute(
        """
        INSERT OR REPLACE INTO balance_notify (wallet, url)
        VALUES (?, ?)
        """,
        (wallet_id, url),
    )


async def get_balance_notify(
    wallet_id: str,
    conn: Optional[Connection] = None,
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
