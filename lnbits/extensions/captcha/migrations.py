async def m001_initial(db):
    """
    Initial captchas table.
    """
    await db.execute(
        """
        CREATE TABLE captcha.captchas (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            secret TEXT NOT NULL,
            url TEXT NOT NULL,
            memo TEXT NOT NULL,
            amount INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )


async def m002_redux(db):
    """
    Creates an improved captchas table and migrates the existing data.
    """
    await db.execute("ALTER TABLE captcha.captchas RENAME TO captchas_old")
    await db.execute(
        """
        CREATE TABLE captcha.captchas (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            url TEXT NOT NULL,
            memo TEXT NOT NULL,
            description TEXT NULL,
            amount INTEGER DEFAULT 0,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """,
            remembers INTEGER DEFAULT 0,
            extras TEXT NULL
        );
    """
    )

    for row in [
        list(row) for row in await db.fetchall("SELECT * FROM captcha.captchas_old")
    ]:
        await db.execute(
            """
            INSERT INTO captcha.captchas (
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

    await db.execute("DROP TABLE captcha.captchas_old")
