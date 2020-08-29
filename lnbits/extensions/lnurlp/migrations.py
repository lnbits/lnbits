from lnbits.db import open_ext_db


def m001_initial(db):
    """
    Initial pay table.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pay_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL,
            served_meta INTEGER NOT NULL,
            served_pr INTEGER NOT NULL
        );
        """
    )


def migrate():
    with open_ext_db("lnurlp") as db:
        m001_initial(db)
