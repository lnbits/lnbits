from typing import Optional

from lnbits.core.db import db

from ..models import WebPushSubscription


async def get_webpush_subscription(
    endpoint: str, user: str
) -> Optional[WebPushSubscription]:
    return await db.fetchone(
        """
        SELECT * FROM webpush_subscriptions
        WHERE endpoint = :endpoint AND "user" = :user
        """,
        {"endpoint": endpoint, "user": user},
        WebPushSubscription,
    )


async def get_webpush_subscriptions_for_user(user: str) -> list[WebPushSubscription]:
    return await db.fetchall(
        """SELECT * FROM webpush_subscriptions WHERE "user" = :user""",
        {"user": user},
        WebPushSubscription,
    )


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
