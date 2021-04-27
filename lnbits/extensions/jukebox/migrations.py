async def m001_initial(db):
    """
    Initial jukebox table.
    """
    await db.execute(
        """
        CREATE TABLE jukebox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            user TEXT NOT NULL,
            secret TEXT NOT NULL,
            token TEXT NOT NULL,
            playlists TEXT NOT NULL
        );
        """
    )