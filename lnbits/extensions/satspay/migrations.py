async def m001_initial(db):
    """
    Initial wallet table.
    """

    await db.execute(
        """
        CREATE TABLE satspay.charges (
            id TEXT NOT NULL PRIMARY KEY,
            "user" TEXT,
            description TEXT,
            onchainwallet TEXT,
            onchainaddress TEXT,
            lnbitswallet TEXT,
            payment_request TEXT,
            payment_hash TEXT,
            webhook TEXT,
            completelink TEXT,
            completelinktext TEXT,
            time INTEGER,
            amount INTEGER,
            balance INTEGER DEFAULT 0,
            timestamp TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )


async def m003_add_themes_table(db):
    """
    Themes table
    """

    await db.execute(
        """
        CREATE TABLE satspay.themes (
            css_id TEXT,
            user TEXT,
            title TEXT,
            custom_css TEXT
        );
    """
    )


async def m004_add_custom_css_to_charges(db):
    """
    Add custom css option column to the 'charges' table
    """

    await db.execute("ALTER TABLE satspay.charges ADD COLUMN custom_css TEXT;")
