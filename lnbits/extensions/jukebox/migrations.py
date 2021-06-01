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
            price INTEGER,
            profit INTEGER
        );
        """
    )
async def m002_initial(db):
    """
    Initial jukebox_payment table.
    """
    await db.execute(
        """
        CREATE TABLE jukebox_payment (
            payment_hash TEXT PRIMARY KEY,
            song_id TEXT,
            paid BOOL
        );
        """
    )
async def m003_initial(db):
    """
    Initial jukebox_queue table.
    """
    await db.execute(
        """
        CREATE TABLE jukebox_queue (
            jukebox_id TEXT PRIMARY KEY,
            queue TEXT
        );
        """
    )