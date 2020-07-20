from datetime import datetime

from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash


def m001_initial(db):
    """
    Creates an improved withdraw table and migrates the existing data.
    """
    db.execute(
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
    """)
 

def migrate():
    with open_ext_db("withdraw") as db:
        m001_initial(db)

