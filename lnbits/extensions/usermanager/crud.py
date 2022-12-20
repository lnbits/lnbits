from typing import List, Optional

from lnbits.core.crud import (
    create_account,
    create_wallet,
    delete_wallet,
    get_payments,
    get_user,
)
from lnbits.core.models import Payment

from . import db
from .models import CreateUserData, User, Wallet


async def create_usermanager_user(data: CreateUserData) -> User:
    account = await create_account()
    user = await get_user(account.id)
    assert user, "Newly created user couldn't be retrieved"

    wallet = await create_wallet(user_id=user.id, wallet_name=data.wallet_name)

    await db.execute(
        """
        INSERT INTO usermanager.users (id, name, admin, email, password)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user.id, data.user_name, data.admin_id, data.email, data.password),
    )

    await db.execute(
        """
        INSERT INTO usermanager.wallets (id, admin, name, "user", adminkey, inkey)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            wallet.id,
            data.admin_id,
            data.wallet_name,
            user.id,
            wallet.adminkey,
            wallet.inkey,
        ),
    )

    user_created = await get_usermanager_user(user.id)
    assert user_created, "Newly created user couldn't be retrieved"
    return user_created


async def get_usermanager_user(user_id: str) -> Optional[User]:
    row = await db.fetchone("SELECT * FROM usermanager.users WHERE id = ?", (user_id,))
    return User(**row) if row else None


async def get_usermanager_users(user_id: str) -> List[User]:
    rows = await db.fetchall(
        "SELECT * FROM usermanager.users WHERE admin = ?", (user_id,)
    )

    return [User(**row) for row in rows]


async def delete_usermanager_user(user_id: str, delete_core: bool = True) -> None:
    if delete_core:
        wallets = await get_usermanager_wallets(user_id)
        for wallet in wallets:
            await delete_wallet(user_id=user_id, wallet_id=wallet.id)

    await db.execute("DELETE FROM usermanager.users WHERE id = ?", (user_id,))
    await db.execute("""DELETE FROM usermanager.wallets WHERE "user" = ?""", (user_id,))


async def create_usermanager_wallet(
    user_id: str, wallet_name: str, admin_id: str
) -> Wallet:
    wallet = await create_wallet(user_id=user_id, wallet_name=wallet_name)
    await db.execute(
        """
        INSERT INTO usermanager.wallets (id, admin, name, "user", adminkey, inkey)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (wallet.id, admin_id, wallet_name, user_id, wallet.adminkey, wallet.inkey),
    )
    wallet_created = await get_usermanager_wallet(wallet.id)
    assert wallet_created, "Newly created wallet couldn't be retrieved"
    return wallet_created


async def get_usermanager_wallet(wallet_id: str) -> Optional[Wallet]:
    row = await db.fetchone(
        "SELECT * FROM usermanager.wallets WHERE id = ?", (wallet_id,)
    )
    return Wallet(**row) if row else None


async def get_usermanager_wallets(admin_id: str) -> List[Wallet]:
    rows = await db.fetchall(
        "SELECT * FROM usermanager.wallets WHERE admin = ?", (admin_id,)
    )
    return [Wallet(**row) for row in rows]


async def get_usermanager_users_wallets(user_id: str) -> List[Wallet]:
    rows = await db.fetchall(
        """SELECT * FROM usermanager.wallets WHERE "user" = ?""", (user_id,)
    )
    return [Wallet(**row) for row in rows]


async def get_usermanager_wallet_transactions(wallet_id: str) -> List[Payment]:
    return await get_payments(
        wallet_id=wallet_id, complete=True, pending=False, outgoing=True, incoming=True
    )


async def delete_usermanager_wallet(wallet_id: str, user_id: str) -> None:
    await delete_wallet(user_id=user_id, wallet_id=wallet_id)
    await db.execute("DELETE FROM usermanager.wallets WHERE id = ?", (wallet_id,))
