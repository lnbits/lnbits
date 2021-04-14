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
            wallet TEXT,
            animation1 TEXT,
            animation2 TEXT,
            animation3 TEXT,
            animation1threshold INTEGER,
            animation2threshold INTEGER,
            animation3threshold INTEGER,
            animation1webhook TEXT,
            animation2webhook TEXT,
            animation3webhook TEXT,
            lnurl_title TEXT,
            show_message INTEGER,
            show_ack INTEGER,
            amount_made INTEGER,
            fullscreen_cam INTEGER,
            iframe_url TEXT,
            notes TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )
