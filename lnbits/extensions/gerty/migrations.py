import time


async def m001_initial(db):
    """
    Initial Gertys table.
    """
    await db.execute(
        """
        CREATE TABLE gerty.gertys (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            refresh_time INT,
            name TEXT NOT NULL,
            lnbits_wallets TEXT,
            mempool_endpoint TEXT,
            exchange TEXT,
            display_preferences TEXT
        );
    """
    )


async def m002_add_utc_offset_col(db):
    """
    support for UTC offset
    """
    await db.execute("ALTER TABLE gerty.gertys ADD COLUMN utc_offset INT;")


async def m003_add_gerty_model_col(db):
    """
    support for Gerty model col
    """
    await db.execute("ALTER TABLE gerty.gertys ADD COLUMN type TEXT;")


#########MEMPOOL MIGRATIONS########


async def m004_initial(db):
    """
    Initial Gertys table.
    """
    await db.execute(
        """
        CREATE TABLE gerty.mempool (
            id TEXT PRIMARY KEY,
            mempool_endpoint TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            data TEXT NOT NULL,
            time TIMESTAMP
        );
    """
    )


async def m005_add_gerty_model_col(db):
    """
    support for Gerty model col
    """
    await db.execute("ALTER TABLE gerty.gertys ADD COLUMN urls TEXT;")


async def m006_add_gerty_model_col(db):
    """
    Add UUID ID's to links and migrates existing data
    """
    await db.execute("ALTER TABLE gerty.mempool RENAME TO mempool_old")
    await db.execute(
        """
        CREATE TABLE gerty.mempool (
            id TEXT PRIMARY KEY,
            mempool_endpoint TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            data TEXT NOT NULL,
            time FLOAT
            );
        """
    )

    for row in [
        list(row) for row in await db.fetchall("SELECT * FROM gerty.mempool_old")
    ]:
        await db.execute(
            """
            INSERT INTO gerty.mempool (
                id,
                mempool_endpoint,
                endpoint,
                data,
                time
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                row[3],
                time.time(),
            ),
        )

    await db.execute("DROP TABLE gerty.mempool_old")
