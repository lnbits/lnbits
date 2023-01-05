async def m001_initial(db):
    """
    Initial Market settings table.
    """
    await db.execute(
        """
        CREATE TABLE market.settings (
            "user" TEXT PRIMARY KEY,
            currency TEXT DEFAULT 'sat',
            fiat_base_multiplier INTEGER DEFAULT 1
        );
    """
    )

    """
    Initial stalls table.
    """
    await db.execute(
        """
        CREATE TABLE market.stalls (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            currency TEXT,
            publickey TEXT,
            relays TEXT,
            shippingzones TEXT NOT NULL,
            rating INTEGER DEFAULT 0
        );
    """
    )

    """
    Initial products table.
    """
    await db.execute(
        f"""
        CREATE TABLE market.products (
            id TEXT PRIMARY KEY,
            stall TEXT NOT NULL REFERENCES {db.references_schema}stalls (id) ON DELETE CASCADE,
            product TEXT NOT NULL,
            categories TEXT,
            description TEXT,
            image TEXT,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            rating INTEGER DEFAULT 0
        );
    """
    )

    """
    Initial zones table.
    """
    await db.execute(
        """
        CREATE TABLE market.zones (
            id TEXT PRIMARY KEY,
            "user" TEXT NOT NULL,
            cost TEXT NOT NULL,
            countries TEXT NOT NULL
        );
    """
    )

    """
    Initial orders table.
    """
    await db.execute(
        f"""
        CREATE TABLE market.orders (
            id {db.serial_primary_key},
            wallet TEXT NOT NULL,
            username TEXT,
            pubkey TEXT,
            shippingzone TEXT NOT NULL,
            address TEXT NOT NULL,
            email TEXT NOT NULL,
            total INTEGER NOT NULL,
            invoiceid TEXT NOT NULL,
            paid BOOLEAN NOT NULL,
            shipped BOOLEAN NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )

    """
    Initial order details table.
    """
    await db.execute(
        f"""
        CREATE TABLE market.order_details (
            id TEXT PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES {db.references_schema}orders (id) ON DELETE CASCADE,
            product_id TEXT NOT NULL REFERENCES {db.references_schema}products (id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL
        );
    """
    )

    """
    Initial market table.
    """
    await db.execute(
        """
        CREATE TABLE market.markets (
            id TEXT PRIMARY KEY,
            usr TEXT NOT NULL,
            name TEXT
        );
    """
    )

    """
    Initial market stalls table.
    """
    await db.execute(
        f"""
        CREATE TABLE market.market_stalls (
            id TEXT PRIMARY KEY,
            marketid TEXT NOT NULL REFERENCES {db.references_schema}markets (id) ON DELETE CASCADE,
            stallid TEXT NOT NULL REFERENCES {db.references_schema}stalls (id) ON DELETE CASCADE
        );
    """
    )

    """
    Initial chat messages table.
    """
    await db.execute(
        f"""
        CREATE TABLE market.messages (
            id {db.serial_primary_key},
            msg TEXT NOT NULL,
            pubkey TEXT NOT NULL,
            id_conversation TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """            
        );
    """
    )

    if db.type != "SQLITE":
        """
        Create indexes for message fetching
        """
        await db.execute(
            "CREATE INDEX idx_messages_timestamp ON market.messages (timestamp DESC)"
        )
        await db.execute(
            "CREATE INDEX idx_messages_conversations ON market.messages (id_conversation)"
        )
