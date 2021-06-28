async def m001_initial(db):
    """
    Initial split payment table.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS targets (
            wallet TEXT NOT NULL,
            source TEXT NOT NULL,
            percent INTEGER NOT NULL CHECK (percent >= 0 AND percent <= 100),
            alias TEXT,

            UNIQUE (source, wallet)
        );
        """
    )
