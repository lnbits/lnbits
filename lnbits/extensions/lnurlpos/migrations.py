async def m001_initial(db):
    """
    Initial lnurlpos table.
    """

    await db.execute(
        f"""
        CREATE TABLE lnurlpos.lnurlposs (
            id TEXT NOT NULL PRIMARY KEY,
            secret NOT NULL TEXT,
            title NOT NULL TEXT,
            wallet NOT NULL TEXT,
            message NOT NULL TEXT,
            currency NOT NULL TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )
