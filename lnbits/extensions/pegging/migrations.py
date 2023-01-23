async def m001_initial(db):
    """
    Initial paywalls table.
    """
    await db.execute(
        f"""
        CREATE TABLE pegging.pegs (
            id TEXT PRIMARY KEY,
            name TEXT,
            wallet TEXT,
            percent INTEGER,
            currency TEXT,
            base_url TEXT,
            api_key TEXT,
            api_secret TEXT,
            api_passphrase TEXT,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
