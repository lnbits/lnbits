from lnbits.db import Database

async def m001_initial(db):
    """
    Initial nostradmin table.
    """
    await db.execute(
        f"""
        CREATE TABLE nostradmin.keys (
            pubkey TEXT NOT NULL PRIMARY KEY,
            privkey TEXT NOT NULL
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE nostradmin.notes (
            id TEXT NOT NULL PRIMARY KEY,
            pubkey TEXT NOT NULL,
            created_at TEXT NOT NULL,
            kind INT NOT NULL,
            tags TEXT NOT NULL,
            content TEXT NOT NULL,
            sig TEXT NOT NULL
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE nostradmin.relays (
            id TEXT NOT NULL PRIMARY KEY,
            relay TEXT NOT NULL
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE nostradmin.relaylists (
            id TEXT NOT NULL PRIMARY KEY DEFAULT 1,
            allowlist TEXT,
            denylist TEXT
        );
    """
    )

    await db.execute(
        """
        INSERT INTO nostradmin.relaylists (
            id,
            denylist
        )
        VALUES (?, ?)
        """,
        ("1", "wss://zucks-meta-relay.com\nwss://nostr.cia.gov",),
    )

    await db.execute(
        f"""
        CREATE TABLE nostradmin.connections (
            id TEXT NOT NULL PRIMARY KEY,
            publickey TEXT NOT NULL,
            relayid TEXT NOT NULL
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE nostradmin.subscribed (
            id TEXT NOT NULL PRIMARY KEY,
            userPubkey TEXT NOT NULL,
            subscribedPubkey TEXT NOT NULL
        );
    """
    )