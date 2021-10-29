async def m001_initial(db):

    await db.execute(
        """
        CREATE TABLE bleskomat.bleskomats (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            api_key_id TEXT NOT NULL,
            api_key_secret TEXT NOT NULL,
            api_key_encoding TEXT NOT NULL,
            name TEXT NOT NULL,
            fiat_currency TEXT NOT NULL,
            exchange_rate_provider TEXT NOT NULL,
            fee TEXT NOT NULL,
            UNIQUE(api_key_id)
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE bleskomat.bleskomat_lnurls (
            id TEXT PRIMARY KEY,
            bleskomat TEXT NOT NULL,
            wallet TEXT NOT NULL,
            hash TEXT NOT NULL,
            tag TEXT NOT NULL,
            params TEXT NOT NULL,
            api_key_id TEXT NOT NULL,
            initial_uses INTEGER DEFAULT 1,
            remaining_uses INTEGER DEFAULT 0,
            created_time INTEGER,
            updated_time INTEGER,
            UNIQUE(hash)
        );
    """
    )
