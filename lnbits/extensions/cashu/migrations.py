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
            tickershort TEXT DEFAULT 'sats',
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

    """
    Initial cashus table.
    """
    await db.execute(
        """
        CREATE TABLE cashu.promises (
            id TEXT PRIMARY KEY,
            amount INT,
            B_b TEXT NOT NULL,
            C_b TEXT NOT NULL,
            cashu_id TEXT NOT NULL
        );
    """
    )

    """
    Initial cashus table.
    """
    await db.execute(
        """
        CREATE TABLE cashu.proofs_used (
            id TEXT PRIMARY KEY,
            amount INT,
            C TEXT NOT NULL,
            secret TEXT NOT NULL,
            cashu_id TEXT NOT NULL
        );
    """
    )

    await db.execute(
        """
            CREATE TABLE IF NOT EXISTS cashu.invoices (
                cashu_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                pr TEXT NOT NULL,
                hash TEXT NOT NULL,
                issued BOOL NOT NULL,

                UNIQUE (hash)

            );
        """
    )
