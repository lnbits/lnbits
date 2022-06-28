async def m001_initial(db):
    """
    Initial split payment table.
    """
    await db.execute(
        """
        CREATE TABLE splitpayments.targets (
            wallet TEXT NOT NULL,
            source TEXT NOT NULL,
            percent INTEGER NOT NULL CHECK (percent >= 0 AND percent <= 100),
            alias TEXT,

            UNIQUE (source, wallet)
        );
        """
    )

async def m002_float_percent(db):
    """
    Add float percent and migrates the existing data.
    """
    await db.execute("ALTER TABLE splitpayments.targets RENAME TO splitpayments_old")
    await db.execute(
        """
        CREATE TABLE splitpayments.targets (
            wallet TEXT NOT NULL,
            source TEXT NOT NULL,
            percent REAL NOT NULL CHECK (percent >= 0 AND percent <= 100),
            alias TEXT,

            UNIQUE (source, wallet)
        );
    """
    )

    for row in [
        list(row) for row in await db.fetchall("SELECT * FROM splitpayments.splitpayments_old")
    ]:
        await db.execute(
            """
            INSERT INTO splitpayments.targets (
                wallet,
                source,
                percent,
                alias
            )
            VALUES (?, ?, ?, ?)
            """,
            (row[0], row[1], row[2], row[3]),
        )

    await db.execute("DROP TABLE splitpayments.splitpayments_old")
