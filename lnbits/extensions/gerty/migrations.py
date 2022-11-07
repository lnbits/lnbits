async def m001_initial(db):
    """
    Initial Gertys table.
    """
    await db.execute(
        """
        CREATE TABLE gerty.gertys (
            id TEXT PRIMARY KEY,
            refresh_time INT,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            lnbits_wallets TEXT,
            mempool_endpoint TEXT,
            exchange TEXT,
            display_preferences TEXT
        );
    """
    )


async def m002_add_utc_offset_col(db):
    """
    support for UTC offset
    """
    await db.execute("ALTER TABLE gerty.gertys ADD COLUMN utc_offset INT;")
