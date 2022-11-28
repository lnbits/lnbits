async def m001_initial(db):
    """
    Initial wallet table.
    """

    await db.execute(
        f"""
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
            amount {db.big_int},
            balance {db.big_int} DEFAULT 0,
            timestamp TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )


async def m002_add_charge_extra_data(db):
    """
    Add 'extra' column for storing various config about the charge (JSON format)
    """
    await db.execute(
        """ALTER TABLE satspay.charges 
            ADD COLUMN extra TEXT DEFAULT '{"mempool_endpoint": "https://mempool.space", "network": "Mainnet"}';
        """
    )


async def m003_add_themes_table(db):
    """
    Themes table
    """

    await db.execute(
        """
        CREATE TABLE satspay.themes (
            css_id TEXT NOT NULL PRIMARY KEY,
            "user" TEXT,
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
