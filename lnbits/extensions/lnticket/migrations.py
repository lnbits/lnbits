from lnbits.db import open_ext_db

def m001_initial(db):

    db.execute(
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

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            paid BOOLEAN NOT NULL,
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

def migrate():
    with open_ext_db("lnticket") as db:
        m001_initial(db)