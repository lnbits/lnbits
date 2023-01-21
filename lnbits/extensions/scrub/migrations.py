async def m001_initial(db):
    """
    Initial scrub table.
    """
    await db.execute(
        """
        CREATE TABLE scrub.scrub_links (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            description TEXT NOT NULL,
            payoraddress TEXT NOT NULL
        );
        """
    )
