async def m001_initial(db):
    """
    Initial livestream tables.
    """
    await db.execute(
        f"""
        CREATE TABLE livestream.livestreams (
            id {db.serial_primary_key},
            wallet TEXT NOT NULL,
            fee_pct INTEGER NOT NULL DEFAULT 10,
            current_track INTEGER
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE livestream.producers (
            livestream INTEGER NOT NULL REFERENCES {db.references_schema}livestreams (id),
            id {db.serial_primary_key},
            "user" TEXT NOT NULL,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE livestream.tracks (
            livestream INTEGER NOT NULL REFERENCES {db.references_schema}livestreams (id),
            id {db.serial_primary_key},
            download_url TEXT,
            price_msat INTEGER NOT NULL DEFAULT 0,
            name TEXT,
            producer INTEGER REFERENCES {db.references_schema}producers (id) NOT NULL
        );
        """
    )
