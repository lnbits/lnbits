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


async def m002_addresses(db):
    await db.execute(
        """
        CREATE TABLE lnaddress.address (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            domain TEXT NOT NULL,
            email TEXT,
            username TEXT NOT NULL,
            wallet_key TEXT NOT NULL,
            wallet_endpoint TEXT NOT NULL,
            sats INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            paid BOOLEAN NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
