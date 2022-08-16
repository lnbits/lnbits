async def m001_initial(db):
    """
    Initial stalls table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.stalls (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            publickey TEXT,
            privatekey TEXT,
            relays TEXT,
            shippingzones TEXT NOT NULL
        );
    """
    )

    """
    Initial products table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.products (
            id TEXT PRIMARY KEY,
            stall TEXT NOT NULL REFERENCES {db.references_schema}stalls (id),
            product TEXT NOT NULL,
            categories TEXT,
            description TEXT,
            image TEXT,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            rating INTEGER NOT NULL
        );
    """
    )

    """
    Initial zones table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.zones (
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
        """
        CREATE TABLE diagonalley.orders (
            id {db.serial_primary_key},
            wallet TEXT NOT NULL,
            pubkey TEXT,
            shippingzone INTEGER NOT NULL,
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
        """
        CREATE TABLE diagonalley.order_details (
            id TEXT PRIMARY KEY,
            orderid INTEGER NOT NULL REFERENCES {db.references_schema}orders (id)
            productid TEXT NOT NULL REFERENCES {db.references_schema}products (id),
            quantity INTEGER NOT NULL
        );
    """
    )

    """
    Initial market table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.markets (
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
        """
        CREATE TABLE diagonalley.market_stalls (
            id TEXT PRIMARY KEY,
            marketid TEXT NOT NULL REFERENCES {db.references_schema}markets (id),
            stallid TEXT NOT NULL REFERENCES {db.references_schema}stalls (id)
        );
    """
    )
    
