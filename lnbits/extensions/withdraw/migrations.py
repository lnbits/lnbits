async def m001_initial(db):
    """
    Creates an improved withdraw table and migrates the existing data.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS withdraw_links (
            id TEXT PRIMARY KEY,
            wallet TEXT,
            title TEXT,
            min_withdrawable INTEGER DEFAULT 1,
            max_withdrawable INTEGER DEFAULT 1,
            uses INTEGER DEFAULT 1,
            wait_time INTEGER,
            is_unique INTEGER DEFAULT 0,
            unique_hash TEXT UNIQUE,
            k1 TEXT,
            open_time INTEGER,
            used INTEGER DEFAULT 0,
            usescsv TEXT
        );
    """
    )


async def m002_change_withdraw_table(db):
    """
    Creates an improved withdraw table and migrates the existing data.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS withdraw_link (
            id TEXT PRIMARY KEY,
            wallet TEXT,
            title TEXT,
            min_withdrawable INTEGER DEFAULT 1,
            max_withdrawable INTEGER DEFAULT 1,
            uses INTEGER DEFAULT 1,
            wait_time INTEGER,
            is_unique INTEGER DEFAULT 0,
            unique_hash TEXT UNIQUE,
            k1 TEXT,
            open_time INTEGER,
            used INTEGER DEFAULT 0,
            usescsv TEXT
        );
        """
    )
    await db.execute("CREATE INDEX IF NOT EXISTS wallet_idx ON withdraw_link (wallet)")
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS unique_hash_idx ON withdraw_link (unique_hash)"
    )

    for row in [list(row) for row in await db.fetchall("SELECT * FROM withdraw_links")]:
        usescsv = ""

        for i in range(row[5]):
            if row[7]:
                usescsv += "," + str(i + 1)
            else:
                usescsv += "," + str(1)
        usescsv = usescsv[1:]
        await db.execute(
            """
            INSERT INTO withdraw_link (
                id,
                wallet,
                title,
                min_withdrawable,
                max_withdrawable,
                uses,
                wait_time,
                is_unique,
                unique_hash,
                k1,
                open_time,
                used,
                usescsv
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                row[10],
                row[11],
                usescsv,
            ),
        )
    await db.execute("DROP TABLE withdraw_links")


async def m003_make_hash_check(db):
    """
    Creates a hash check table.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS hash_check (
            id TEXT PRIMARY KEY,
            lnurl_id TEXT
        );
    """
    )
