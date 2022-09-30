async def m001_initial(db):

    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS hedge.HedgedWallets (
            id {db.serial_primary_key},
            ticker TEXT NOT NULL,
            wallet TEXT NOT NULL,
            onchain TEXT,
            hedgeuri TEXT
        );
        """
    )
