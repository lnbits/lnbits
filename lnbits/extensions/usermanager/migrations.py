from lnbits.db import open_ext_db


def m001_initial(db):
    """
    Initial users table.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            admin TEXT NOT NULL,
            email TEXT,
            password TEXT
        );
    """
    )

    """
    Initial wallets table.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            id TEXT PRIMARY KEY,
            admin TEXT NOT NULL,
            name TEXT NOT NULL,
            user TEXT NOT NULL,
            adminkey TEXT NOT NULL,
            inkey TEXT NOT NULL
        );
    """
    )


def migrate():
    with open_ext_db("usermanager") as db:
        m001_initial(db)
