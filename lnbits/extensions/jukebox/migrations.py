async def m001_initial(db):
    """
    Initial jukebox table.
    """
    await db.execute(
        """
        CREATE TABLE jukebox (
            id TEXT PRIMARY KEY,
            user TEXT,
            title TEXT,
            wallet TEXT,
            sp_user TEXT NOT NULL,
            sp_secret TEXT NOT NULL,
            sp_access_token TEXT,
            sp_refresh_token TEXT,
            sp_device TEXT,
            sp_playlists TEXT,
            price INTEGER
        );
        """
    )
