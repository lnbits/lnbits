from lnbits.db import open_ext_db

def m001_initial(db):

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            info TEXT NOT NULL,
            closing_date TEXT NOT NULL,
            event_start_date TEXT NOT NULL,
            event_end_date TEXT NOT NULL,
            amount_tickets INTEGER NOT NULL,
            price_per_ticket INTEGER NOT NULL,
            sold INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            event TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            registered BOOLEAN NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )


def m002_changed(db):

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            event TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            registered BOOLEAN NOT NULL,
            paid BOOLEAN NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )
    
    for row in [list(row) for row in db.fetchall("SELECT * FROM tickets")]:
        usescsv = ""

        for i in range(row[5]):
            if row[7]:
                usescsv += "," + str(i + 1)
            else:
                usescsv += "," + str(1)
        usescsv = usescsv[1:]  
        db.execute(
            """
            INSERT INTO ticket (
                id,
                wallet,
                event,
                name,
                email,
                registered,
                paid
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
                True,
            ),
        )
    db.execute("DROP TABLE tickets")

def migrate():
    with open_ext_db("events") as db:
        m001_initial(db)
        m002_changed(db)

