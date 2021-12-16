async def m001_initial(db):
    await db.execute(
        """
        CREATE TABLE swap.out (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            onchainwallet TEXT,
            onchainaddress TEXT NOT NULL,
            amount INT NOT NULL,
            recurrent BOOLEAN NOT NULL,
            fee INT NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )

async def m002_add_recurrent(db):
    await db.execute(
        """
        CREATE TABLE swap.recurrent (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            onchainwallet TEXT,
            onchainaddress TEXT NOT NULL,
            threshold INT NOT NULL,
            fee INT NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )

async def m003_add_swap_in(db):
    await db.execute(
        """
        CREATE TABLE swap.in (
            id TEXT PRIMARY KEY, 
            wallet TEXT NOT NULL,
            session_id TEXT NOT NULL,
            reserve_id TEXT NOT NULL,
            txid TEXT,
            amount INT,
            done BOOLEAN NOT NULL DEFAULT FALSE,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
