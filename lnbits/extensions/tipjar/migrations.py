async def m001_initial(db):

    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS tipjar.Jars (
            id {db.serial_primary_key},
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            onchain TEXT,
            webhook TEXT,
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS tipjar.Tips (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            sats INT NOT NULL,
            posted BOOLEAN NOT NULL,
            FOREIGN KEY(jar) REFERENCES {db.references_schema}Jars(id)
        );
        """
    )
