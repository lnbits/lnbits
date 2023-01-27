from . import db
from .models import NostrEvent


async def create_event(relay_id: str, e: NostrEvent):
    await db.execute(
        """
        INSERT INTO nostrrelay.events (
            relay_id,
            id,
            pubkey,
            created_at,
            kind,
            content,
            sig
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (relay_id, e.id, e.pubkey, e.created_at, e.kind, e.content, e.sig),
    )

    # todo: optimize with bulk insert
    for tag in e.tags:
        await create_event_tags(relay_id, e.id, tag[0], tag[1])


async def create_event_tags(
    relay_id: str, event_id: str, tag_name: str, tag_value: str
):
    await db.execute(
        """
        INSERT INTO nostrrelay.event_tags (
            relay_id,
            event_id,
            name,
            value
        )
        VALUES (?, ?, ?, ?)
        """,
        (relay_id, event_id, tag_name, tag_value),
    )
