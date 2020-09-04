def m001_initial(db):
    """
    Initial amilks table.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS amilks (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            lnurl TEXT NOT NULL,
            atime INTEGER NOT NULL,
            amount INTEGER NOT NULL
        );
    """
    )
