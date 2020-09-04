from sqlite3 import OperationalError


def m001_initial(db):
    """
    Initial paywalls table.
    """
    db.execute(
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


def m002_redux(db):
    """
    Creates an improved paywalls table and migrates the existing data.
    """
    try:
        db.execute("SELECT remembers FROM paywalls")

    except OperationalError:
        db.execute("ALTER TABLE paywalls RENAME TO paywalls_old")
        db.execute(
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
        db.execute("CREATE INDEX IF NOT EXISTS wallet_idx ON paywalls (wallet)")

        for row in [list(row) for row in db.fetchall("SELECT * FROM paywalls_old")]:
            db.execute(
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

        db.execute("DROP TABLE paywalls_old")
