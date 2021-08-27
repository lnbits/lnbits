async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE lnaddress.domain (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            domain TEXT NOT NULL,
            webhook TEXT,
            cf_token TEXT NOT NULL,
            cf_zone_id TEXT NOT NULL,
            cost INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
