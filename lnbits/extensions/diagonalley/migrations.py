async def m001_initial(db):
    """
    Initial products table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.products (
            id TEXT PRIMARY KEY,
            stall TEXT NOT NULL,
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
    Initial stalls table.
    """
    await db.execute(
        """
        CREATE TABLE diagonalley.stalls (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            publickey TEXT NOT NULL,
            privatekey TEXT NOT NULL,
            relays TEXT NOT NULL
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
            wallet TEXT NOT NULL,
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
