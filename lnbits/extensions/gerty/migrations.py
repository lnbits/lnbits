async def m001_initial(db):
    """
    Initial gertys table.
    """
    await db.execute(
        """
        CREATE TABLE gerty.gertys (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            lnbits_wallets TEXT NOT NULL,
            sats_quote BOOL NOT NULL,
            exchange TEXT NOT NULL,
            onchain_sats BOOL NOT NULL,
            ln_stats BOOL NOT NULL
        );
    """
    )