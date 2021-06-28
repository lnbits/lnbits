async def m001_initial(db):
    """
    Initial offlineshop tables.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            method TEXT NOT NULL,
            wordlist TEXT
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            shop INTEGER NOT NULL REFERENCES shop (id),
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT, -- image/png;base64,...
            enabled BOOLEAN NOT NULL DEFAULT true,
            price INTEGER NOT NULL,
            unit TEXT NOT NULL DEFAULT 'sat'
        );
        """
    )
