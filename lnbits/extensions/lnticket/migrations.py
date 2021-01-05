async def m001_initial(db):

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS forms (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            costpword INTEGER NOT NULL,
            amountmade INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            form TEXT NOT NULL,
            email TEXT NOT NULL,
            ltext TEXT NOT NULL,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            sats INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )


async def m002_changed(db):

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket (
            id TEXT PRIMARY KEY,
            form TEXT NOT NULL,
            email TEXT NOT NULL,
            ltext TEXT NOT NULL,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            sats INTEGER NOT NULL,
            paid BOOLEAN NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )

    for row in [list(row) for row in await db.fetchall("SELECT * FROM tickets")]:
        usescsv = ""

        for i in range(row[5]):
            if row[7]:
                usescsv += "," + str(i + 1)
            else:
                usescsv += "," + str(1)
        usescsv = usescsv[1:]
        await db.execute(
            """
            INSERT INTO ticket (
                id,
                form,
                email,
                ltext,
                name,
                wallet,
                sats,
                paid
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                True,
            ),
        )
    await db.execute("DROP TABLE tickets")


async def m003_changed(db):

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS form (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            webhook TEXT,
            description TEXT NOT NULL,
            costpword INTEGER NOT NULL,
            amountmade INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )

    for row in [list(row) for row in await db.fetchall("SELECT * FROM forms")]:
        usescsv = ""

        for i in range(row[5]):
            if row[7]:
                usescsv += "," + str(i + 1)
            else:
                usescsv += "," + str(1)
        usescsv = usescsv[1:]
        await db.execute(
            """
            INSERT INTO form (
                id,
                wallet,
                name,
                webhook,
                description,
                costpword,
                amountmade
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
            ),
        )
    await db.execute("DROP TABLE forms")
