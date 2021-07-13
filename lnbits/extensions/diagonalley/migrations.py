async def m001_initial(db):
    """
    Initial products table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.products (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            product TEXT NOT NULL,
            categories TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL
        );
    """
    )

    """
    Initial indexers table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.indexers (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            shopname TEXT NOT NULL,
            indexeraddress TEXT NOT NULL,
            online BOOLEAN NOT NULL,
            rating INTEGER NOT NULL,
            shippingzone1 TEXT NOT NULL,
            shippingzone2 TEXT NOT NULL,
            zone1cost INTEGER NOT NULL,
            zone2cost INTEGER NOT NULL,
            email TEXT NOT NULL
        );
    """
    )

    """
    Initial orders table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.orders (
            id TEXT PRIMARY KEY,
            productid TEXT NOT NULL,
            wallet TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            shippingzone INTEGER NOT NULL,
            address TEXT NOT NULL,
            email TEXT NOT NULL,
            invoiceid TEXT NOT NULL,
            paid BOOLEAN NOT NULL,
            shipped BOOLEAN NOT NULL
        );
    """
    )
