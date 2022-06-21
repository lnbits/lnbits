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
from .models import CreateUserData, Users, Wallets

### Users


async def create_discordbot_user(data: CreateUserData) -> Users:
    account = await create_account()
    user = await get_user(account.id)
    assert user, "Newly created user couldn't be retrieved"

    wallet = await create_wallet(user_id=user.id, wallet_name=data.wallet_name)

    await db.execute(
        """
        INSERT INTO discordbot.users (id, name, admin, discord_id)
        VALUES (?, ?, ?, ?)
        """,
        (user.id, data.user_name, data.admin_id, data.discord_id),
    )

    await db.execute(
        """
        INSERT INTO discordbot.wallets (id, admin, name, "user", adminkey, inkey)
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

    user_created = await get_discordbot_user(user.id)
    assert user_created, "Newly created user couldn't be retrieved"
    return user_created


async def get_discordbot_user(user_id: str) -> Optional[Users]:
    row = await db.fetchone("SELECT * FROM discordbot.users WHERE id = ?", (user_id,))
    return Users(**row) if row else None


async def get_discordbot_users(user_id: str) -> List[Users]:
    rows = await db.fetchall(
        "SELECT * FROM discordbot.users WHERE admin = ?", (user_id,)
    )

    return [Users(**row) for row in rows]


async def delete_discordbot_user(user_id: str) -> None:
    wallets = await get_discordbot_wallets(user_id)
    for wallet in wallets:
        await delete_wallet(user_id=user_id, wallet_id=wallet.id)

    await db.execute("DELETE FROM discordbot.users WHERE id = ?", (user_id,))
    await db.execute("""DELETE FROM discordbot.wallets WHERE "user" = ?""", (user_id,))


### Wallets


async def create_discordbot_wallet(
    user_id: str, wallet_name: str, admin_id: str
) -> Wallets:
    wallet = await create_wallet(user_id=user_id, wallet_name=wallet_name)
    await db.execute(
        """
        INSERT INTO discordbot.wallets (id, admin, name, "user", adminkey, inkey)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (wallet.id, admin_id, wallet_name, user_id, wallet.adminkey, wallet.inkey),
    )
    wallet_created = await get_discordbot_wallet(wallet.id)
    assert wallet_created, "Newly created wallet couldn't be retrieved"
    return wallet_created


async def get_discordbot_wallet(wallet_id: str) -> Optional[Wallets]:
    row = await db.fetchone(
        "SELECT * FROM discordbot.wallets WHERE id = ?", (wallet_id,)
    )
    return Wallets(**row) if row else None


async def get_discordbot_wallets(admin_id: str) -> Optional[Wallets]:
    rows = await db.fetchall(
        "SELECT * FROM discordbot.wallets WHERE admin = ?", (admin_id,)
    )
    return [Wallets(**row) for row in rows]


async def get_discordbot_users_wallets(user_id: str) -> Optional[Wallets]:
    rows = await db.fetchall(
        """SELECT * FROM discordbot.wallets WHERE "user" = ?""", (user_id,)
    )
    return [Wallets(**row) for row in rows]


async def get_discordbot_wallet_transactions(wallet_id: str) -> Optional[Payment]:
    return await get_payments(
        wallet_id=wallet_id, complete=True, pending=False, outgoing=True, incoming=True
    )


async def delete_discordbot_wallet(wallet_id: str, user_id: str) -> None:
    await delete_wallet(user_id=user_id, wallet_id=wallet_id)
    await db.execute("DELETE FROM discordbot.wallets WHERE id = ?", (wallet_id,))
