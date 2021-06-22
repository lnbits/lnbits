async def m001_initial(db):
    """
    Initial offlineshop tables.
    """
    await db.execute(
        f"""
        CREATE TABLE offlineshop.shops (
            id {db.serial_primary_key},
            wallet TEXT NOT NULL,
            method TEXT NOT NULL,
            wordlist TEXT
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE offlineshop.items (
            shop INTEGER NOT NULL REFERENCES {db.references_schema}shops (id),
            id {db.serial_primary_key},
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT, -- image/png;base64,...
            enabled BOOLEAN NOT NULL DEFAULT true,
            price INTEGER NOT NULL,
            unit TEXT NOT NULL DEFAULT 'sat'
        );
        """
    )
