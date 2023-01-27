from typing import Any, List

from . import db
from .models import NostrEvent, NostrFilter


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


async def get_events(relay_id: str, filter: NostrFilter) -> List[NostrEvent]:
    query = "SELECT * FROM nostrrelay.events WHERE relay_id = ?"
    values: List[Any] = [relay_id]
    if len(filter.ids) != 0:
        ids = ",".join(["?"] * len(filter.ids))
        query += f" AND id IN ({ids})"
        values += filter.ids
    if len(filter.authors) != 0:
        authors = ",".join(["?"] * len(filter.authors))
        query += f" AND pubkey IN ({authors})"
        values += filter.authors
    if len(filter.kinds) != 0:
        kinds = ",".join(["?"] * len(filter.kinds))
        query += f" AND kind IN ({kinds})"
        values += filter.kinds
    if filter.since:
        query += f" AND created_at >= ?"
        values += [filter.since]
    if filter.until:
        query += f" AND created_at <= ?"
        values += [filter.until]

    query += " ORDER BY created_at DESC"
    if filter.limit and type(filter.limit) == int and filter.limit > 0:
        query += f" LIMIT {filter.limit}"

    # print("### query: ", query)
    # print("### values: ", tuple(values))
    rows = await db.fetchall(query, tuple(values))
    events = [NostrEvent.from_row(row) for row in rows]

    # print("### events: ", len(events))

    return events
