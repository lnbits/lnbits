import json
import datetime
from uuid import uuid4
from typing import List, Optional, Dict, Any

from lnbits import bolt11
from lnbits.settings import DEFAULT_WALLET_NAME

from . import db
from .models import User, Wallet, Payment


# accounts
# --------


async def create_account() -> User:
    user_id = uuid4().hex
    await db.execute("INSERT INTO accounts (id) VALUES (?)", (user_id,))

    new_account = await get_account(user_id=user_id)
    assert new_account, "Newly created account couldn't be retrieved"

    return new_account


async def get_account(user_id: str) -> Optional[User]:
    row = await db.fetchone(
        "SELECT id, email, pass as password FROM accounts WHERE id = ?", (user_id,)
    )

    return User(**row) if row else None


async def get_user(user_id: str) -> Optional[User]:
    user = await db.fetchone("SELECT id, email FROM accounts WHERE id = ?", (user_id,))

    if user:
        extensions = await db.fetchall(
            "SELECT extension FROM extensions WHERE user = ? AND active = 1", (user_id,)
        )
        wallets = await db.fetchall(
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


async def update_user_extension(*, user_id: str, extension: str, active: int) -> None:
    await db.execute(
        """
        INSERT OR REPLACE INTO extensions (user, extension, active)
        VALUES (?, ?, ?)
        """,
        (user_id, extension, active),
    )


# wallets
# -------


async def create_wallet(*, user_id: str, wallet_name: Optional[str] = None) -> Wallet:
    wallet_id = uuid4().hex
    await db.execute(
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

    new_wallet = await get_wallet(wallet_id=wallet_id)
    assert new_wallet, "Newly created wallet couldn't be retrieved"

    return new_wallet


async def delete_wallet(*, user_id: str, wallet_id: str) -> None:
    await db.execute(
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


async def get_wallet(wallet_id: str) -> Optional[Wallet]:
    row = await db.fetchone(
        """
        SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) AS balance_msat
        FROM wallets
        WHERE id = ?
        """,
        (wallet_id,),
    )

    return Wallet(**row) if row else None


async def get_wallet_for_key(key: str, key_type: str = "invoice") -> Optional[Wallet]:
    row = await db.fetchone(
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


async def get_standalone_payment(checking_id_or_hash: str) -> Optional[Payment]:
    row = await db.fetchone(
        """
        SELECT *
        FROM apipayments
        WHERE checking_id = ? OR hash = ?
        LIMIT 1
        """,
        (checking_id_or_hash, checking_id_or_hash),
    )

    return Payment.from_row(row) if row else None


async def get_wallet_payment(wallet_id: str, payment_hash: str) -> Optional[Payment]:
    row = await db.fetchone(
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

    rows = await db.fetchall(
        f"""
        SELECT *
        FROM apipayments
        {where}
        ORDER BY time DESC
        """,
        tuple(args),
    )

    return [Payment.from_row(row) for row in rows]


async def delete_expired_invoices() -> None:
    rows = await db.fetchall(
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

        await db.execute(
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
) -> Payment:
    await db.execute(
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

    new_payment = await get_wallet_payment(wallet_id, payment_hash)
    assert new_payment, "Newly created payment couldn't be retrieved"

    return new_payment


async def update_payment_status(checking_id: str, pending: bool) -> None:
    await db.execute(
        "UPDATE apipayments SET pending = ? WHERE checking_id = ?",
        (
            int(pending),
            checking_id,
        ),
    )


async def delete_payment(checking_id: str) -> None:
    await db.execute("DELETE FROM apipayments WHERE checking_id = ?", (checking_id,))


async def check_internal(payment_hash: str) -> Optional[str]:
    row = await db.fetchone(
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
