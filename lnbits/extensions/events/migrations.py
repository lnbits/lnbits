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

def migrate():
    with open_ext_db("events") as db:
        m001_initial(db)

