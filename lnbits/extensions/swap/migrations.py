async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE swap.out (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            onchainwallet TEXT,
            onchainaddress TEXT NOT NULL,
            amount INT NOT NULL,
            recurrent BOOLEAN NOT NULL,
            fee INT NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
