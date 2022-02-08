from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash
import shortuuid
from . import db
from .models import (
    nostrKeys,
    nostrNotes,
    nostrCreateRelays,
    nostrRelays,
    nostrConnections,
    nostrCreateConnections,
    nostrRelayList,
)

###############KEYS##################


async def create_nostrkeys(data: nostrKeys) -> nostrKeys:
    await db.execute(
        """
        INSERT INTO nostradmin.keys (
            pubkey,
            privkey
        )
        VALUES (?, ?)
        """,
        (data.pubkey, data.privkey),
    )
    return await get_nostrkeys(nostrkey_id)


async def get_nostrkeys(pubkey: str) -> nostrKeys:
    row = await db.fetchone("SELECT * FROM nostradmin.keys WHERE pubkey = ?", (pubkey,))
    return nostrKeys(**row) if row else None


###############NOTES##################


async def create_nostrnotes(data: nostrNotes) -> nostrNotes:
    await db.execute(
        """
        INSERT INTO nostradmin.notes (
            id,
            pubkey,
            created_at,
            kind,
            tags,
            content,
            sig
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.id,
            data.pubkey,
            data.created_at,
            data.kind,
            data.tags,
            data.content,
            data.sig,
        ),
    )
    return await get_nostrnotes(data.id)


async def get_nostrnotes(nostrnote_id: str) -> nostrNotes:
    row = await db.fetchone("SELECT * FROM nostradmin.notes WHERE id = ?", (nostrnote_id,))
    return nostrNotes(**row) if row else None


###############RELAYS##################


async def create_nostrrelays(data: nostrCreateRelays) -> nostrCreateRelays:
    nostrrelay_id = shortuuid.uuid(name=data.relay)

    if await get_nostrrelay(nostrrelay_id):
        return "error"
    await db.execute(
        """
        INSERT INTO nostradmin.relays (
            id,
            relay
        )
        VALUES (?, ?)
        """,
        (nostrrelay_id, data.relay),
    )
    return await get_nostrrelay(nostrrelay_id)


async def get_nostrrelays() -> nostrRelays:
    rows = await db.fetchall("SELECT * FROM nostradmin.relays")
    return [nostrRelays(**row) for row in rows]


async def get_nostrrelay(nostrrelay_id: str) -> nostrRelays:
    row = await db.fetchone("SELECT * FROM nostradmin.relays WHERE id = ?", (nostrrelay_id,))
    return nostrRelays(**row) if row else None


async def update_nostrrelayallowlist(allowlist: str) -> nostrRelayList:
    await db.execute(
        """
        UPDATE nostradmin.relaylist SET
          allowlist = ?
        WHERE id = ?
        """,
        (allowlist, 1),
    )
    return await get_nostrrelaylist()

async def update_nostrrelaydenylist(denylist: str) -> nostrRelayList:
    await db.execute(
        """
        UPDATE nostradmin.relaylist SET
          denylist = ?
        WHERE id = ?
        """,
        (denylist, 1),
    )
    return await get_nostrrelaylist()

async def get_nostrrelaylist() -> nostrRelayList:
    row = await db.fetchone("SELECT * FROM nostradmin.relaylist WHERE id = ?", (1,))
    return nostrRelayList(**row) if row else None


###############CONNECTIONS##################


async def create_nostrconnections(
    data: nostrCreateConnections
) -> nostrCreateConnections:
    nostrrelay_id = shortuuid.uuid(name=data.relayid + data.pubkey)
    await db.execute(
        """
        INSERT INTO nostradmin.connections (
            id,
            pubkey,
            relayid
        )
        VALUES (?, ?, ?)
        """,
        (data.id, data.pubkey, data.relayid),
    )
    return await get_nostrconnections(data.id)


async def get_nostrconnections(nostrconnections_id: str) -> nostrConnections:
    row = await db.fetchone(
        "SELECT * FROM nostradmin.connections WHERE id = ?", (nostrconnections_id,)
    )
    return nostrConnections(**row) if row else None
