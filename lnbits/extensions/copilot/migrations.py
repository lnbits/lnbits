async def m001_initial(db):
    """
    Initial copilot table.
    """

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS copilots (
            id TEXT NOT NULL PRIMARY KEY,
            user TEXT,
            title TEXT,
            animation INTEGER,
            show_message TEXT,
            amount INTEGER,
            lnurl_title TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )
