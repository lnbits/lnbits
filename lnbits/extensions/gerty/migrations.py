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
