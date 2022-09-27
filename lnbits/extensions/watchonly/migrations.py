async def m001_initial(db):
    """
    Initial wallet table.
    """
    await db.execute(
        """
        CREATE TABLE watchonly.wallets (
            id TEXT NOT NULL PRIMARY KEY,
            "user" TEXT,
            masterpub TEXT NOT NULL,
            title TEXT NOT NULL,
            address_no INTEGER NOT NULL DEFAULT 0,
            balance INTEGER NOT NULL
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE watchonly.addresses (
            id TEXT NOT NULL PRIMARY KEY,
            address TEXT NOT NULL,
            wallet TEXT NOT NULL,
            amount INTEGER NOT NULL
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE watchonly.mempool (
            "user" TEXT NOT NULL,
            endpoint TEXT NOT NULL 
        );
    """
    )


async def m002_add_columns_to_adresses(db):
    """
    Add 'branch_index', 'address_index', 'has_activity' and 'note' columns to the 'addresses' table
    """

    await db.execute(
        "ALTER TABLE watchonly.addresses ADD COLUMN branch_index INTEGER NOT NULL DEFAULT 0;"
    )
    await db.execute(
        "ALTER TABLE watchonly.addresses ADD COLUMN address_index INTEGER NOT NULL DEFAULT 0;"
    )
    await db.execute(
        "ALTER TABLE watchonly.addresses ADD COLUMN has_activity BOOLEAN DEFAULT false;"
    )
    await db.execute("ALTER TABLE watchonly.addresses ADD COLUMN note TEXT;")


async def m003_add_columns_to_wallets(db):
    """
    Add 'type' and 'fingerprint' columns to the 'wallets' table
    """

    await db.execute("ALTER TABLE watchonly.wallets ADD COLUMN type TEXT;")
    await db.execute(
        "ALTER TABLE watchonly.wallets ADD COLUMN fingerprint TEXT NOT NULL DEFAULT '';"
    )


async def m004_create_config_table(db):
    """
    Allow the extension to persist and retrieve any number of config values.
    Each user has its configurations saved as a JSON string
    """

    await db.execute(
        """CREATE TABLE watchonly.config (
            "user" TEXT NOT NULL,
            json_data TEXT NOT NULL
        );"""
    )


async def m005_add_network_column_to_wallets(db):
    """
    Add network' column to the 'wallets' table
    """

    await db.execute(
        "ALTER TABLE watchonly.wallets ADD COLUMN network TEXT DEFAULT 'Mainnet';"
    )


async def m006_drop_mempool_table(db):
    """
    Mempool data is now part of `config`
    """
    await db.execute("DROP TABLE watchonly.mempool;")


async def m007_add_wallet_meta_data(db):
    """
    Add 'meta' for storing various metadata about the wallet
    """
    await db.execute("ALTER TABLE watchonly.wallets ADD COLUMN meta TEXT DEFAULT '{}';")
