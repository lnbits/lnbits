from lnbits.db import open_ext_db


def m001_initial(db):
    """
    Initial paywalls table.
    """
    db.execute("""
        CREATE TABLE IF NOT EXISTS paywalls (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            url TEXT NOT NULL,
            memo TEXT NOT NULL,
            amount INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """)


def migrate():
    with open_ext_db("tpos") as db:
        m001_initial(db)
