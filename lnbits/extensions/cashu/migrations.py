async def m001_initial(db):
    """
    Initial cashu table.
    """
    await db.execute(
        """
        CREATE TABLE cashu.cashu (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            tickershort TEXT NOT NULL,
            fraction BOOL,
            maxsats INT,
            coins INT,
            prvkey TEXT NOT NULL,
            pubkey TEXT NOT NULL
        );
    """
    )

    """
    Initial cashus table.
    """
    await db.execute(
        """
        CREATE TABLE cashu.pegs (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            inout BOOL NOT NULL,
            amount INT
        );
    """
    )

