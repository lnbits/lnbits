from sqlalchemy.exc import OperationalError  # type: ignore


async def m001_initial(db):
    """
    Initial paywalls table.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS paywalls (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            secret TEXT NOT NULL,
            url TEXT NOT NULL,
            memo TEXT NOT NULL,
            amount INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )


async def m002_redux(db):
    """
    Creates an improved paywalls table and migrates the existing data.
    """
    try:
        await db.execute("SELECT remembers FROM paywalls")

    except OperationalError:
        await db.execute("ALTER TABLE paywalls RENAME TO paywalls_old")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS paywalls (
                id TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                url TEXT NOT NULL,
                memo TEXT NOT NULL,
                description TEXT NULL,
                amount INTEGER DEFAULT 0,
                time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now')),
                remembers INTEGER DEFAULT 0,
                extras TEXT NULL
            );
        """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS wallet_idx ON paywalls (wallet)")

        for row in [
            list(row) for row in await db.fetchall("SELECT * FROM paywalls_old")
        ]:
            await db.execute(
                """
                INSERT INTO paywalls (
                    id,
                    wallet,
                    url,
                    memo,
                    amount,
                    time
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (row[0], row[1], row[3], row[4], row[5], row[6]),
            )

        await db.execute("DROP TABLE paywalls_old")
