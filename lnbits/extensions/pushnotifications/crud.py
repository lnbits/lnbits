import json

from . import db
from .models import Subscription
from typing import List, Optional


async def get_subscription(
    endpoint: str, wallet: str
) -> Optional[Subscription]:
    row = await db.fetchone(
        "SELECT * FROM pushnotifications.subscriptions WHERE endpoint = ? AND wallet = ?", (endpoint, wallet,)
    )
    return Subscription(**dict(row)) if row else None


async def get_subscriptions_by_endpoint(endpoint: str) -> List[Subscription]:
    rows = await db.fetchall(
        "SELECT * FROM pushnotifications.subscriptions WHERE endpoint = ?", (endpoint,)
    )
    return [Subscription(**dict(row)) for row in rows]


async def get_subscriptions_by_wallet(wallet: str) -> List[Subscription]:
    rows = await db.fetchall(
        "SELECT * FROM pushnotifications.subscriptions WHERE wallet = ?", (wallet,)
    )
    return [Subscription(**dict(row)) for row in rows]


async def create_subscription(
    endpoint: str, wallet: str, data: str, host: str
) -> Subscription:
    await db.execute(
        """
        INSERT INTO pushnotifications.subscriptions (endpoint, wallet, data, host)
        VALUES (?, ?, ?, ?)
        """,
        (endpoint, wallet, data, host, )
    )
    subscription = await get_subscription(endpoint, wallet)
    assert subscription, "Newly created subscription couldn't be retrieved"
    return subscription


async def delete_subscriptions(endpoint: str) -> None:
    """
    Delete subscriptions of all wallets registered to this endpoint.
    """
    await db.execute("DELETE FROM pushnotifications.subscriptions WHERE endpoint = ?", (endpoint,))
