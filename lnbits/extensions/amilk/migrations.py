async def m001_initial(db):
    """
    Initial amilks table.
    """
    await db.execute(
        """
        CREATE TABLE amilk.amilks (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            lnurl TEXT NOT NULL,
            atime INTEGER NOT NULL,
            amount INTEGER NOT NULL
        );
    """
    )
