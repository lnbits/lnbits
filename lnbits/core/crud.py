import json
import datetime
from uuid import uuid4
from typing import List, Optional, Dict
from flask import g

from lnbits import bolt11
from lnbits.settings import DEFAULT_WALLET_NAME

from .models import User, Wallet, Payment, Admin, Funding


# accounts
# --------


def create_account() -> User:
    user_id = uuid4().hex
    g.db.execute("INSERT INTO accounts (id) VALUES (?)", (user_id,))

    new_account = get_account(user_id=user_id)
    assert new_account, "Newly created account couldn't be retrieved"

    return new_account

def get_account(user_id: str) -> Optional[User]:
    row = g.db.fetchone("SELECT id, email, pass as password FROM accounts WHERE id = ?", (user_id,))

    return User(**row) if row else None


def get_user(user_id: str) -> Optional[User]:
    user = g.db.fetchone("SELECT id, email FROM accounts WHERE id = ?", (user_id,))

    if user:
        extensions = g.db.fetchall("SELECT extension FROM extensions WHERE user = ? AND active = 1", (user_id,))
        wallets = g.db.fetchall(
            """
            SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) AS balance_msat
            FROM wallets
            WHERE user = ?
            """,
            (user_id,),
        )

    return (
        User(**{**user, **{"extensions": [e[0] for e in extensions], "wallets": [Wallet(**w) for w in wallets]}})
        if user
        else None
    )


def update_user_extension(*, user_id: str, extension: str, active: int) -> None:
    g.db.execute(
        """
        INSERT OR REPLACE INTO extensions (user, extension, active)
        VALUES (?, ?, ?)
        """,
        (user_id, extension, active),
    )


# wallets
# -------


def create_wallet(*, user_id: str, wallet_name: Optional[str] = None) -> Wallet:
    wallet_id = uuid4().hex
    g.db.execute(
        """
        INSERT INTO wallets (id, name, user, adminkey, inkey)
        VALUES (?, ?, ?, ?, ?)
        """,
        (wallet_id, wallet_name or DEFAULT_WALLET_NAME, user_id, uuid4().hex, uuid4().hex),
    )

    new_wallet = get_wallet(wallet_id=wallet_id)
    assert new_wallet, "Newly created wallet couldn't be retrieved"

    return new_wallet


def delete_wallet(*, user_id: str, wallet_id: str) -> None:
    g.db.execute(
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
    row = g.db.fetchone(
        """
        SELECT *, COALESCE((SELECT balance FROM balances WHERE wallet = wallets.id), 0) AS balance_msat
        FROM wallets
        WHERE id = ?
        """,
        (wallet_id,),
    )

    return Wallet(**row) if row else None


def get_wallet_for_key(key: str, key_type: str = "invoice") -> Optional[Wallet]:
    row = g.db.fetchone(
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


def get_wallet_payment(wallet_id: str, payment_hash: str) -> Optional[Payment]:
    row = g.db.fetchone(
        """
        SELECT *
        FROM apipayments
        WHERE wallet = ? AND hash = ?
        """,
        (wallet_id, payment_hash),
    )

    return Payment.from_row(row) if row else None


def get_wallet_payments(
    wallet_id: str,
    *,
    complete: bool = False,
    pending: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    exclude_uncheckable: bool = False,
) -> List[Payment]:
    """
    Filters payments to be returned by complete | pending | outgoing | incoming.
    """

    clause = ""
    if complete and pending:
        clause += ""
    elif complete:
        clause += "AND ((amount > 0 AND pending = 0) OR amount < 0)"
    elif pending:
        clause += "AND pending = 1"
    else:
        raise TypeError("at least one of [complete, pending] must be True.")

    clause += " "

    if outgoing and incoming:
        clause += ""
    elif outgoing:
        clause += "AND amount < 0"
    elif incoming:
        clause += "AND amount > 0"
    else:
        raise TypeError("at least one of [outgoing, incoming] must be True.")

    clause += " "

    if exclude_uncheckable:  # checkable means it has a checking_id that isn't internal
        clause += "AND checking_id NOT LIKE 'temp_%' "
        clause += "AND checking_id NOT LIKE 'internal_%' "

    rows = g.db.fetchall(
        f"""
        SELECT *
        FROM apipayments
        WHERE wallet = ? {clause}
        ORDER BY time DESC
        """,
        (wallet_id,),
    )

    return [Payment.from_row(row) for row in rows]


def delete_expired_invoices() -> None:
    rows = g.db.fetchall(
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

        g.db.execute(
            """
            DELETE FROM apipayments
            WHERE pending = 1 AND hash = ?
            """,
            (invoice.payment_hash,),
        )


# payments
# --------


def create_payment(
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
) -> Payment:
    g.db.execute(
        """
        INSERT INTO apipayments
          (wallet, checking_id, bolt11, hash, preimage,
           amount, pending, memo, fee, extra)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json.dumps(extra) if extra and extra != {} and type(extra) is dict else None,
        ),
    )

    new_payment = get_wallet_payment(wallet_id, payment_hash)
    assert new_payment, "Newly created payment couldn't be retrieved"

    return new_payment


def update_payment_status(checking_id: str, pending: bool) -> None:
    g.db.execute(
        "UPDATE apipayments SET pending = ? WHERE checking_id = ?",
        (
            int(pending),
            checking_id,
        ),
    )


def delete_payment(checking_id: str) -> None:
    g.db.execute("DELETE FROM apipayments WHERE checking_id = ?", (checking_id,))


def check_internal(payment_hash: str) -> Optional[str]:
    row = g.db.fetchone(
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

# admin
# --------

def get_admin(
    user: Optional[str] = None, 
    site_title: Optional[str] = None,
    tagline: Optional[str] = None,
    primary_color: Optional[str] = None, 
    secondary_color: Optional[str] = None,
    allowed_users: Optional[str] = None, 
    default_wallet_name: Optional[str] = None,
    data_folder: Optional[str] = None, 
    disabled_ext: Optional[str] = "amilk",
    force_https: Optional[bool] = True,     
    service_fee: Optional[int] = 0,
    funding_source_primary: Optional[str] = "",
    edited: Optional[str] = "",
    CLightningWallet: Optional[str] =  '',
    LndRestWallet: Optional[str] =  '',
    LndWallet: Optional[str] =  '',
    LntxbotWallet: Optional[str] =  '',
    LNPayWallet: Optional[str] =  '',
    LnbitsWallet: Optional[str] =  '',
    OpenNodeWallet: Optional[str] =  '',

    ) -> Optional[Admin]:
    row = g.db.fetchone("SELECT * FROM admin WHERE 1")
    if not user:
        return Admin(**row) if row else None
    if not row[0] or user != None:
        g.db.execute(
            """
            UPDATE admin
            SET user = ?, site_title = ?, tagline = ?, primary_color = ?, secondary_color = ?, allowed_users = ?, default_wallet_name = ?, data_folder = ?, disabled_ext = ?, force_https = ?, service_fee = ?, funding_source = ?
            WHERE 1
            """,
            (
                user,
                site_title,
                tagline,
                primary_color,
                secondary_color,
                allowed_users,
                default_wallet_name,
                data_folder,
                disabled_ext,
                force_https,
                service_fee,
                funding_source_primary,
           ),
        )
        row = g.db.fetchone("SELECT * FROM admin WHERE 1")
    return Admin(**row) if row else None

def get_funding(
    edited: Optional[str] = "",
    CLightningWallet: Optional[str] =  '',
    LndRestWallet: Optional[str] =  '',
    LndWallet: Optional[str] =  '',
    LntxbotWallet: Optional[str] =  '',
    LNPayWallet: Optional[str] =  '',
    LnbitsWallet: Optional[str] =  '',
    OpenNodeWallet: Optional[str] =  '',
    ) -> List[Funding]:
    if edited:
        edited.split(",")
        CLightningWallet.split(",")
        LndRestWallet.split(",")
        LndWallet.split(",")
        LntxbotWallet.split(",")
        LNPayWallet.split(",")
        LnbitsWallet.split(",")
        OpenNodeWallet.split(",")
        print(OpenNodeWallet)

    rows = g.db.fetchall("SELECT * FROM funding")
    return [Funding(**row) for row in rows]


