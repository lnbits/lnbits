from datetime import datetime
from uuid import uuid4

from lnbits.db import open_ext_db


def m001_initial(db):
    """
    Initial withdraw table.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS withdraws (
            key INTEGER PRIMARY KEY AUTOINCREMENT,
            usr TEXT,
            wal TEXT,
            walnme TEXT,
            adm INTEGER,
            uni TEXT,
            tit TEXT,
            maxamt INTEGER,
            minamt INTEGER,
            spent INTEGER,
            inc INTEGER,
            tme INTEGER,
            uniq INTEGER DEFAULT 0,
            withdrawals TEXT,
            tmestmp INTEGER,
            rand TEXT
        );
        """
    )


def migrate():
    with open_ext_db("withdraw") as db:
        m001_initial(db)
