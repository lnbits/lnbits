from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash
import shortuuid
from . import db
from .models import nostrKeys, nostrNotes, nostrCreateRelays, nostrRelays, nostrConnections, nostrCreateConnections

###############KEYS##################

async def create_nostrkeys(
    data: nostrKeys
) -> nostrKeys:
    await db.execute(
        """
        INSERT INTO nostr.keys (
            pubkey,
            privkey
        )
        VALUES (?, ?)
        """,
        (data.pubkey, data.privkey),
    )
    return await get_nostrkeys(nostrkey_id)

async def get_nostrkeys(pubkey: str) -> nostrKeys:
    row = await db.fetchone(
        "SELECT * FROM nostr.keys WHERE pubkey = ?",
        (pubkey,),
    )
    return nostrKeys(**row) if row else None


###############NOTES##################

async def create_nostrnotes(
    data: nostrNotes
) -> nostrNotes:
    await db.execute(
        """
        INSERT INTO nostr.notes (
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
        (data.id, data.pubkey, data.created_at, data.kind, data.tags, data.content, data.sig),
    )
    return await get_nostrnotes(data.id)

async def get_nostrnotes(nostrnote_id: str) -> nostrNotes:
    row = await db.fetchone(
        "SELECT * FROM nostr.notes WHERE id = ?",
        (nostrnote_id,),
    )
    return nostrNotes(**row) if row else None

###############RELAYS##################

async def create_nostrrelays(
    data: nostrCreateRelays
) -> nostrCreateRelays:
    nostrrelay_id = shortuuid.uuid(name=relay)
    
    if await get_nostrrelays(nostrrelay_id):
        return "error"
    await db.execute(
        """
        INSERT INTO nostr.relays (
            id,
            relay
        )
        VALUES (?, ?)
        """,
        (nostrrelay_id, data.relay),
    )
    return await get_nostrnotes(nostrrelay_id)

async def get_nostrrelays(nostrrelay_id: str) -> nostrRelays:
    row = await db.fetchone(
        "SELECT * FROM nostr.relays WHERE id = ?",
        (nostrnote_id,),
    )
    return nostrRelays(**row) if row else None


###############CONNECTIONS##################

async def create_nostrconnections(
    data: nostrCreateConnections
) -> nostrCreateConnections:
    nostrrelay_id = shortuuid.uuid(name=data.relayid + data.pubkey)
    await db.execute(
        """
        INSERT INTO nostr.connections (
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
        "SELECT * FROM nostr.connections WHERE id = ?",
        (nostrconnections_id,),
    )
    return nostrConnections(**row) if row else None