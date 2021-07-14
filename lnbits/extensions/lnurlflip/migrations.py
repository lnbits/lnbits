async def m001_initial(db):
    """
    Creates an improved lnurlflip table and migrates the existing data.
    """
    await db.execute(
        """
        CREATE TABLE lnurlflip.lnurlflip_pay (
            id TEXT PRIMARY KEY,
            wallet TEXT,
            title TEXT,
            value INTEGER DEFAULT 1,
            unique_hash TEXT UNIQUE,
            k1 TEXT,
            odds FLOAT,
            current_odds FLOAT,
            open_time INTEGER
        );
    """
    )


async def m002_initial(db):
    """
    Creates an improved lnurlflip table and migrates the existing data.
    """
    await db.execute(
        """
        CREATE TABLE lnurlflip.lnurlflip_withdraw (
            id TEXT PRIMARY KEY,
            wallet TEXT,
            pay TEXT,
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
        CREATE TABLE lnurlflip.hash_check (
            id TEXT PRIMARY KEY,
            lnurl_id TEXT
        );
    """
    )
