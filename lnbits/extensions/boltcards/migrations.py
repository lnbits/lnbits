from lnbits.helpers import urlsafe_short_hash

async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE boltcards.cards (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            card_name TEXT NOT NULL,
            uid TEXT NOT NULL,
            counter INT NOT NULL DEFAULT 0,
            withdraw TEXT NOT NULL,
            file_key TEXT NOT NULL DEFAULT '00000000000000000000000000000000',
            meta_key TEXT NOT NULL DEFAULT '',
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
