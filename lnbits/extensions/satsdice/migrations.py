async def m001_initial(db):
    """
    Creates an improved satsdice table and migrates the existing data.
    """
    await db.execute(
        """
        CREATE TABLE satsdice.satsdice_pay (
            id TEXT PRIMARY KEY,
            wallet TEXT,
            title TEXT,
            min_bet INTEGER,
            max_bet INTEGER,
            amount INTEGER DEFAULT 0,
            served_meta INTEGER NOT NULL,
            served_pr INTEGER NOT NULL,
            multiplier FLOAT,
            chance FLOAT,
            base_url TEXT,
            open_time INTEGER
        );
    """
    )


async def m002_initial(db):
    """
    Creates an improved satsdice table and migrates the existing data.
    """
    await db.execute(
        """
        CREATE TABLE satsdice.satsdice_withdraw (
            id TEXT PRIMARY KEY,
            satsdice_pay TEXT,
            value INTEGER DEFAULT 1,
            unique_hash TEXT UNIQUE,
            k1 TEXT,
            open_time INTEGER,
            used INTEGER DEFAULT 0
        );
    """
    )


async def m003_make_hash_check(db):
    """
    Creates a hash check table.
    """
    await db.execute(
        """
        CREATE TABLE satsdice.hash_check (
            id TEXT PRIMARY KEY,
            lnurl_id TEXT
        );
    """
    )
