async def m001_initial(db):
    """
    Initial wallet table.
    """

    await db.execute(
        """
        CREATE TABLE satspay.charges (
            id TEXT NOT NULL PRIMARY KEY,
            "user" TEXT,
            description TEXT,
            onchainwallet TEXT,
            onchainaddress TEXT,
            lnbitswallet TEXT,
            payment_request TEXT,
            payment_hash TEXT,
            webhook TEXT,
            completelink TEXT,
            completelinktext TEXT,
            time INTEGER,
            amount INTEGER,
            balance INTEGER DEFAULT 0,
            timestamp TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
