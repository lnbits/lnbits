from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import nostrKeys, nostrNotes, nostrRelays, nostrConnections

###############KEYS##################

async def create_nostrkeys(
    data: nostrKeys
) -> nostrKeys:
    nostrkey_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO nostr.keys (
            id,
            pubkey,
            privkey
        )
        VALUES (?, ?, ?)
        """,
        (nostrkey_id, data.pubkey, data.privkey),
    )
    return await get_nostrkeys(nostrkey_id)

async def get_nostrkeys(nostrkey_id: str) -> nostrKeys:
    row = await db.fetchone(
        "SELECT * FROM nostr.keys WHERE id = ?",
        (lnurldevicepayment_id,),
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
    relay: str
) -> nostrRelays:
    nostrrelay_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO nostr.relays (
            id,
            relay
        )
        VALUES (?, ?)
        """,
        (nostrrelay_id, relay),
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
    data: nostrNotes
) -> nostrNotes:
    nostrkey_id = urlsafe_short_hash()
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



async def update_lnurldevicepayment(
    lnurldevicepayment_id: str, **kwargs
) -> Optional[lnurldevicepayment]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnurldevice.lnurldevicepayment SET {q} WHERE id = ?",
        (*kwargs.values(), lnurldevicepayment_id),
    )
    row = await db.fetchone(
        "SELECT * FROM lnurldevice.lnurldevicepayment WHERE id = ?",
        (lnurldevicepayment_id,),
    )
    return lnurldevicepayment(**row) if row else None