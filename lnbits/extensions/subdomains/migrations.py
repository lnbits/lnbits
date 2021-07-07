async def m001_initial(db):

    await db.execute(
        """
        CREATE TABLE subdomains.domain (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            domain TEXT NOT NULL,
            webhook TEXT,
            cf_token TEXT NOT NULL,
            cf_zone_id TEXT NOT NULL,
            description TEXT NOT NULL,
            cost INTEGER NOT NULL,
            amountmade INTEGER NOT NULL,
            allowed_record_types TEXT NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE subdomains.subdomain (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            email TEXT NOT NULL,
            subdomain TEXT NOT NULL,
            ip TEXT NOT NULL,
            wallet TEXT NOT NULL,
            sats INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            paid BOOLEAN NOT NULL,
            record_type TEXT NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
