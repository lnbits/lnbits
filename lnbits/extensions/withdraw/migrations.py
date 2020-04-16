from datetime import datetime

from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash


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


def m002_change_withdraw_table(db):
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
            used INTEGER DEFAULT 0
        );
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS wallet_idx ON withdraw_links (wallet)")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS unique_hash_idx ON withdraw_links (unique_hash)")

    for row in [list(row) for row in db.fetchall("SELECT * FROM withdraws")]:
        db.execute(
            """
            INSERT INTO withdraw_links (
                id,
                wallet,
                title,
                min_withdrawable,
                max_withdrawable,
                uses,
                wait_time,
                is_unique,
                unique_hash,
                k1,
                open_time,
                used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[5],  # uni
                row[2],  # wal
                row[6],  # tit
                row[8],  # minamt
                row[7],  # maxamt
                row[10],  # inc
                row[11],  # tme
                row[12],  # uniq
                urlsafe_short_hash(),
                urlsafe_short_hash(),
                int(datetime.now().timestamp()) + row[11],
                row[9],  # spent
            ),
        )
    db.execute("DROP TABLE withdraws")


def migrate():
    with open_ext_db("withdraw") as db:
        m001_initial(db)
        m002_change_withdraw_table(db)
