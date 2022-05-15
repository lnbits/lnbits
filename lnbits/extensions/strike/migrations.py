async def m001_initial(db):
    """
    Initial tables
    """

    await db.execute(
        """
        CREATE TABLE strike.configurations (
            id TEXT NOT NULL PRIMARY KEY,
            lnbits_wallet TEXT,
            handle TEXT,
            description TEXT,
            currency TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE strike.forwards (
            id TEXT NOT NULL PRIMARY KEY,
            lnbits_wallet TEXT,
            handle TEXT,
            message TEXT,
            sats_original INT NOT NULL,
            sats_forwarded INT,
            amount REAL NOT NULL,
            currency TEXT,
            spread REAL,
            status TEXT,
            status_info TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )

async def m002_add_fee_column(db):
    """
    Support for payment fess
    """
    await db.execute(
        "ALTER TABLE strike.forwards ADD COLUMN msats_fee INTEGER DEFAULT 0;"
    )