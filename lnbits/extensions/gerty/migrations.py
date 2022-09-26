async def m001_initial(db):
    """
    Initial gertys table.
    """
    await db.execute(
        """
        CREATE TABLE gerty.gertys (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            lnbits_wallets TEXT,
            sats_quote BOOL,
            exchange TEXT,
            onchain_stats BOOL,
            ln_stats BOOL
        );
    """
    )