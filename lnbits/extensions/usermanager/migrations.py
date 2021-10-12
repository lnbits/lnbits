async def m001_initial(db):
    """
    Initial users table.
    """
    await db.execute(
        """
        CREATE TABLE usermanager.users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            admin TEXT NOT NULL,
            email TEXT,
            password TEXT
        );
    """
    )

    """
    Initial wallets table.
    """
    await db.execute(
        """
        CREATE TABLE usermanager.wallets (
            id TEXT PRIMARY KEY,
            admin TEXT NOT NULL,
            name TEXT NOT NULL,
            "user" TEXT NOT NULL,
            adminkey TEXT NOT NULL,
            inkey TEXT NOT NULL
        );
    """
    )
