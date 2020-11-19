async def m001_initial(db):
    """
    Initial livestream tables.
    """
    await db.execute(
        """
        CREATE TABLE livestreams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            fee_pct INTEGER NOT NULL DEFAULT 10,
            current_track INTEGER
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE producers (
            livestream INTEGER NOT NULL REFERENCES livestreams (id),
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE tracks (
            livestream INTEGER NOT NULL REFERENCES livestreams (id),
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            download_url TEXT,
            price_msat INTEGER NOT NULL DEFAULT 0,
            name TEXT,
            producer INTEGER REFERENCES producers (id) NOT NULL
        );
        """
    )
