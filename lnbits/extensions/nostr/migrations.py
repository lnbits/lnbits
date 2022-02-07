from lnbits.db import Database

db2 = Database("ext_nostr")


async def m001_initial(db):
    """
    Initial nostr table.
    """
    await db.execute(
        f"""
        CREATE TABLE nostr.keys (
            pubkey TEXT NOT NULL PRIMARY KEY,
            privkey TEXT NOT NULL
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE nostr.notes (
            id TEXT NOT NULL PRIMARY KEY,
            pubkey TEXT NOT NULL,
            created_at TEXT NOT NULL,
            kind INT NOT NULL,
            tags TEXT NOT NULL,
            content TEXT NOT NULL,
            sig TEXT NOT NULL,
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE nostr.relays (
            id TEXT NOT NULL PRIMARY KEY,
            relay TEXT NOT NULL
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE nostr.connections (
            id TEXT NOT NULL PRIMARY KEY,
            publickey TEXT NOT NULL,
            relayid TEXT NOT NULL
        );
    """
    )