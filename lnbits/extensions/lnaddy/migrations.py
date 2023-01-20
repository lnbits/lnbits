async def m001_initial(db):
    """
    Initial ln address paylink table.
    """
    await db.execute(
        f"""
        CREATE TABLE lnaddy.pay_links (
            id {db.serial_primary_key},
            wallet TEXT NOT NULL,
            wallet_key TEXT NOT NULL,
            description TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            served_meta INTEGER NOT NULL,
            served_pr INTEGER NOT NULL,
            lnaddress TEXT NOT NULL
        );
        """
    )


async def m002_webhooks_and_success_actions(db):
    """
    Webhooks and success actions.
    """
    await db.execute("ALTER TABLE lnaddy.pay_links ADD COLUMN webhook_url TEXT;")
    await db.execute("ALTER TABLE lnaddy.pay_links ADD COLUMN success_text TEXT;")
    await db.execute("ALTER TABLE lnaddy.pay_links ADD COLUMN success_url TEXT;")
    await db.execute(
        f"""
        CREATE TABLE lnaddy.invoices (
            pay_link INTEGER NOT NULL REFERENCES {db.references_schema}pay_links (id),
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
        "ALTER TABLE lnaddy.pay_links ADD COLUMN currency TEXT;"
    )  # null = satoshis
    await db.execute(
        "ALTER TABLE lnaddy.pay_links ADD COLUMN comment_chars INTEGER DEFAULT 0;"
    )
    await db.execute("ALTER TABLE lnaddy.pay_links RENAME COLUMN amount TO min;")
    await db.execute("ALTER TABLE lnaddy.pay_links ADD COLUMN max INTEGER;")
    await db.execute("UPDATE lnaddy.pay_links SET max = min;")
    await db.execute("DROP TABLE lnaddy.invoices")


async def m004_fiat_base_multiplier(db):
    """
    Store the multiplier for fiat prices. We store the price in cents and
    remember to multiply by 100 when we use it to convert to Dollars.
    """
    await db.execute(
        "ALTER TABLE lnaddy.pay_links ADD COLUMN fiat_base_multiplier INTEGER DEFAULT 1;"
    )


async def m005_webhook_headers_and_body(db):
    """
    Add headers and body to webhooks
    """
    await db.execute("ALTER TABLE lnaddy.pay_links ADD COLUMN webhook_headers TEXT;")
    await db.execute("ALTER TABLE lnaddy.pay_links ADD COLUMN webhook_body TEXT;")
