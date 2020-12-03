async def m001_initial(db):
    """
    Initial wallet table.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            id TEXT NOT NULL PRIMARY KEY,
            user TEXT,
            masterpub TEXT NOT NULL,
            title TEXT NOT NULL,
            address_no INTEGER NOT NULL DEFAULT 0,
            amount INTEGER NOT NULL
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS addresses (
            address TEXT NOT NULL PRIMARY KEY,
            wallet TEXT NOT NULL,
            amount INTEGER NOT NULL
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT NOT NULL PRIMARY KEY,
            user TEXT,
            title TEXT,
            wallet TEXT NOT NULL,
            address TEXT NOT NULL,
            time_to_pay INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS mempool (
            user TEXT NOT NULL,
            endpoint TEXT NOT NULL 
        );
    """
    )