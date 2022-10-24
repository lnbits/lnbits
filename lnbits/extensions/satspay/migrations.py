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


async def m002_add_charge_extra_data(db):
    """
    Add 'extra' column for storing various config about the charge (JSON format)
    """
    await db.execute(
        """ALTER TABLE satspay.charges 
            ADD COLUMN extra TEXT DEFAULT '{"mempool_endpoint": "https://mempool.space", "network": "Mainnet"}';
        """
    )

async def m002_add_settings_table(db):
    """
    Settings table
    """

    await db.execute(
        """
        CREATE TABLE satspay.settings (
            id TEXT NOT NULL PRIMARY KEY,
            "user" TEXT,
            custom_css TEXT
        );
    """
    )
