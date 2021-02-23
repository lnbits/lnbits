async def m001_initial(db):
    """
    Initial wallet table.
    """


    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS charges (
            id TEXT NOT NULL PRIMARY KEY,
            user TEXT,
            title TEXT,
            wallet TEXT NOT NULL,
            address TEXT NOT NULL,
            time_to_pay INTEGER,
            amount INTEGER,
            balance INTEGER DEFAULT 0,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )