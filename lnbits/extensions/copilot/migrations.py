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
            animation1 TEXT,
            animation2 TEXT,
            animation3 TEXT,
            animation1threshold INTEGER,
            animation2threshold INTEGER,
            animation3threshold INTEGER,
            show_message TEXT,
            amount INTEGER,
            lnurl_title TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )
