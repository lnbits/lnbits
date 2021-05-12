async def m001_initial(db): 
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS setup (
            usr_id TEXT PRIMARY KEY,
            invoice_wallet TEXT NOT NULL,
            payout_wallet TEXT NOT NULL,
            data TEXT,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
        """
        )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            usr_id TEXT PRIMARY KEY,
            id TEXT NOT NULL,
            payout_wallet TEXT NOT NULL,
            credits INTEGER NOT NULL,
            active BOOLEAN NOT NULL,
            data TEXT,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
        """
        )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usr TEXT NOT NULL,
            cmd TEXT NOT NULL,
            wl TEXT,
            credits INTEGER,
            multi INTEGER,
            sats INTEGER,
            data TEXT,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
        """
        )
