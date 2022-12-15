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
            price {db.big_int} NOT NULL,
            unit TEXT NOT NULL DEFAULT 'sat'
        );
        """
    )


async def m002_fiat_base_multiplier(db):
    """
    Store the multiplier for fiat prices. We store the price in cents and
    remember to multiply by 100 when we use it to convert to Dollars.
    """
    await db.execute(
        "ALTER TABLE offlineshop.items ADD COLUMN fiat_base_multiplier INTEGER DEFAULT 1;"
    )
