from typing import List, Optional
from uuid import uuid4

from lnbits.db import open_db
from lnbits.settings import DEFAULT_WALLET_NAME, FEE_RESERVE

from .models import User, Wallet, Payment


# accounts
# --------


def create_account() -> User:
    with open_db() as db:
        user_id = uuid4().hex
        db.execute("INSERT INTO accounts (id) VALUES (?)", (user_id,))

    return get_account(user_id=user_id)


def get_account(user_id: str) -> Optional[User]:
    with open_db() as db:
        row = db.fetchone("SELECT id, email, pass as password FROM accounts WHERE id = ?", (user_id,))

    return User(**row) if row else None


def get_user(user_id: str) -> Optional[User]:
    with open_db() as db:
        user = db.fetchone("SELECT id, email FROM accounts WHERE id = ?", (user_id,))

        if user:
            extensions = db.fetchall("SELECT extension FROM extensions WHERE user = ? AND active = 1", (user_id,))
            wallets = db.fetchall(
                """
                SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) * ? AS balance_msat
                FROM wallets
                WHERE user = ?
                """,
                (1 - FEE_RESERVE, user_id),
            )

    return (
        User(**{**user, **{"extensions": [e[0] for e in extensions], "wallets": [Wallet(**w) for w in wallets]}})
        if user
        else None
    )


def update_user_extension(*, user_id: str, extension: str, active: int) -> None:
    with open_db() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO extensions (user, extension, active)
            VALUES (?, ?, ?)
            """,
            (user_id, extension, active),
        )


# wallets
# -------


def create_wallet(*, user_id: str, wallet_name: Optional[str] = None) -> Wallet:
    with open_db() as db:
        wallet_id = uuid4().hex
        db.execute(
            """
            INSERT INTO wallets (id, name, user, adminkey, inkey)
            VALUES (?, ?, ?, ?, ?)
            """,
            (wallet_id, wallet_name or DEFAULT_WALLET_NAME, user_id, uuid4().hex, uuid4().hex),
        )

    return get_wallet(wallet_id=wallet_id)


def delete_wallet(*, user_id: str, wallet_id: str) -> None:
    with open_db() as db:
        db.execute(
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


def get_wallet(wallet_id: str) -> Optional[Wallet]:
    with open_db() as db:
        row = db.fetchone(
            """
            SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) * ? AS balance_msat
            FROM wallets
            WHERE id = ?
            """,
            (1 - FEE_RESERVE, wallet_id),
        )

    return Wallet(**row) if row else None


def get_wallet_for_key(key: str, key_type: str = "invoice") -> Optional[Wallet]:
    with open_db() as db:
        check_field = "adminkey" if key_type == "admin" else "inkey"
        row = db.fetchone(
            f"""
            SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) * ? AS balance_msat
            FROM wallets
            WHERE {check_field} = ?
            """,
            (1 - FEE_RESERVE, key),
        )

    return Wallet(**row) if row else None


# wallet payments
# ---------------


def get_wallet_payment(wallet_id: str, checking_id: str) -> Optional[Payment]:
    with open_db() as db:
        row = db.fetchone(
            """
            SELECT payhash as checking_id, amount, fee, pending, memo, time
            FROM apipayments
            WHERE wallet = ? AND payhash = ?
            """,
            (wallet_id, checking_id),
        )

    return Payment(**row) if row else None


def get_wallet_payments(wallet_id: str, *, include_all_pending: bool = False) -> List[Payment]:
    with open_db() as db:
        if include_all_pending:
            clause = "pending = 1"
        else:
            clause = "((amount > 0 AND pending = 0) OR amount < 0)"

        rows = db.fetchall(
            f"""
            SELECT payhash as checking_id, amount, fee, pending, memo, time
            FROM apipayments
            WHERE wallet = ? AND {clause}
            ORDER BY time DESC
            """,
            (wallet_id,),
        )

    return [Payment(**row) for row in rows]


# payments
# --------


def create_payment(
    *, wallet_id: str, checking_id: str, amount: str, memo: str, fee: int = 0, pending: bool = True
) -> Payment:
    with open_db() as db:
        db.execute(
            """
            INSERT INTO apipayments (wallet, payhash, amount, pending, memo, fee)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wallet_id, checking_id, amount, int(pending), memo, fee),
        )

    return get_wallet_payment(wallet_id, checking_id)


def update_payment_status(checking_id: str, pending: bool) -> None:
    with open_db() as db:
        db.execute("UPDATE apipayments SET pending = ? WHERE payhash = ?", (int(pending), checking_id,))


def delete_payment(checking_id: str) -> None:
    with open_db() as db:
        db.execute("DELETE FROM apipayments WHERE payhash = ?", (checking_id,))
