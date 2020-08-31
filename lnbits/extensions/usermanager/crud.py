from lnbits.db import open_ext_db
from lnbits.settings import WALLET
from .models import Users, Wallets
from typing import List, Optional, Union

from ...core.crud import (
    create_account,
    get_user,
    update_user_extension,
    get_wallet_payments,
    create_wallet,
    delete_wallet,
)


###Users


def create_usermanager_user(user_name: str, wallet_name: str, admin_id: str) -> Users:
    user = get_user(create_account().id)

    wallet = create_wallet(user_id=user.id, wallet_name=wallet_name)

    with open_ext_db("usermanager") as db:
        db.execute(
            """
            INSERT INTO users (id, name, admin)
            VALUES (?, ?, ?)
            """,
            (user.id, user_name, admin_id),
        )

        db.execute(
            """
            INSERT INTO wallets (id, admin, name, user, adminkey, inkey)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wallet.id, admin_id, wallet_name, user.id, wallet.adminkey, wallet.inkey),
        )

    return get_usermanager_user(user.id)


def get_usermanager_user(user_id: str) -> Users:
    with open_ext_db("usermanager") as db:

        row = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    return Users(**row) if row else None


def get_usermanager_users(user_id: str) -> Users:

    with open_ext_db("usermanager") as db:
        rows = db.fetchall("SELECT * FROM users WHERE admin = ?", (user_id,))

    return [Users(**row) for row in rows]


def delete_usermanager_user(user_id: str) -> None:
    row = get_usermanager_wallets(user_id)
    print("test")
    with open_ext_db("usermanager") as db:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    row
    for r in row:
        delete_wallet(user_id=user_id, wallet_id=r.id)
    with open_ext_db("usermanager") as dbb:
        dbb.execute("DELETE FROM wallets WHERE user = ?", (user_id,))


###Wallets


def create_usermanager_wallet(user_id: str, wallet_name: str, admin_id: str) -> Wallets:
    wallet = create_wallet(user_id=user_id, wallet_name=wallet_name)
    with open_ext_db("usermanager") as db:

        db.execute(
            """
            INSERT INTO wallets (id, admin, name, user, adminkey, inkey)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wallet.id, admin_id, wallet_name, user_id, wallet.adminkey, wallet.inkey),
        )

    return get_usermanager_wallet(wallet.id)


def get_usermanager_wallet(wallet_id: str) -> Optional[Wallets]:
    with open_ext_db("usermanager") as db:
        row = db.fetchone("SELECT * FROM wallets WHERE id = ?", (wallet_id,))

    return Wallets(**row) if row else None


def get_usermanager_wallets(user_id: str) -> Wallets:

    with open_ext_db("usermanager") as db:
        rows = db.fetchall("SELECT * FROM wallets WHERE admin = ?", (user_id,))

    return [Wallets(**row) for row in rows]


def get_usermanager_wallet_transactions(wallet_id: str) -> Users:
    return get_wallet_payments(wallet_id=wallet_id, include_all_pending=False)


def get_usermanager_wallet_balances(user_id: str) -> Users:
    user = get_user(user_id)
    return user.wallets


def delete_usermanager_wallet(wallet_id: str, user_id: str) -> None:
    delete_wallet(user_id=user_id, wallet_id=wallet_id)
    with open_ext_db("usermanager") as db:
        db.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))
