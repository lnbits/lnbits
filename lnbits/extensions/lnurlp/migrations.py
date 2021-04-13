async def m001_initial(db):
    """
    Initial pay table.
    """
    await db.execute(
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


async def m002_webhooks_and_success_actions(db):
    """
    Webhooks and success actions.
    """
    await db.execute("ALTER TABLE pay_links ADD COLUMN webhook_url TEXT;")
    await db.execute("ALTER TABLE pay_links ADD COLUMN success_text TEXT;")
    await db.execute("ALTER TABLE pay_links ADD COLUMN success_url TEXT;")
    await db.execute(
        """
        CREATE TABLE invoices (
            pay_link INTEGER NOT NULL REFERENCES pay_links (id),
            payment_hash TEXT NOT NULL,
            webhook_sent INT, -- null means not sent, otherwise store status
            expiry INT
        );
        """
    )


async def m003_min_max_comment_fiat(db):
    """
    Support for min/max amounts, comments and fiat prices that get
    converted automatically to satoshis based on some API.
    """
    await db.execute(
        "ALTER TABLE pay_links ADD COLUMN currency TEXT;"
    )  # null = satoshis
    await db.execute(
        "ALTER TABLE pay_links ADD COLUMN comment_chars INTEGER DEFAULT 0;"
    )
    await db.execute("ALTER TABLE pay_links RENAME COLUMN amount TO min;")
    await db.execute("ALTER TABLE pay_links ADD COLUMN max INTEGER;")
    await db.execute("UPDATE pay_links SET max = min;")
    await db.execute("DROP TABLE invoices")
