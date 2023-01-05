async def m001_initial(db):
    """
    Initial pay table.
    """
    await db.execute(
        f"""
        CREATE TABLE lnurlp.pay_links (
            id {db.serial_primary_key},
            wallet TEXT NOT NULL,
            description TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            served_meta INTEGER NOT NULL,
            served_pr INTEGER NOT NULL
        );
        """
    )


async def m002_webhooks_and_success_actions(db):
    """
    Webhooks and success actions.
    """
    await db.execute("ALTER TABLE lnurlp.pay_links ADD COLUMN webhook_url TEXT;")
    await db.execute("ALTER TABLE lnurlp.pay_links ADD COLUMN success_text TEXT;")
    await db.execute("ALTER TABLE lnurlp.pay_links ADD COLUMN success_url TEXT;")
    await db.execute(
        f"""
        CREATE TABLE lnurlp.invoices (
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
        "ALTER TABLE lnurlp.pay_links ADD COLUMN currency TEXT;"
    )  # null = satoshis
    await db.execute(
        "ALTER TABLE lnurlp.pay_links ADD COLUMN comment_chars INTEGER DEFAULT 0;"
    )
    await db.execute("ALTER TABLE lnurlp.pay_links RENAME COLUMN amount TO min;")
    await db.execute("ALTER TABLE lnurlp.pay_links ADD COLUMN max INTEGER;")
    await db.execute("UPDATE lnurlp.pay_links SET max = min;")
    await db.execute("DROP TABLE lnurlp.invoices")


async def m004_fiat_base_multiplier(db):
    """
    Store the multiplier for fiat prices. We store the price in cents and
    remember to multiply by 100 when we use it to convert to Dollars.
    """
    await db.execute(
        "ALTER TABLE lnurlp.pay_links ADD COLUMN fiat_base_multiplier INTEGER DEFAULT 1;"
    )


async def m005_webhook_headers_and_body(db):
    """
    Add headers and body to webhooks
    """
    await db.execute("ALTER TABLE lnurlp.pay_links ADD COLUMN webhook_headers TEXT;")
    await db.execute("ALTER TABLE lnurlp.pay_links ADD COLUMN webhook_body TEXT;")


async def m006_redux(db):
    """
    Add UUID ID's to links and migrates existing data
    """
    await db.execute("ALTER TABLE lnurlp.pay_links RENAME TO pay_links_old")
    await db.execute(
        f"""
        CREATE TABLE lnurlp.pay_links (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            description TEXT NOT NULL,
            min INTEGER NOT NULL,
            max INTEGER,
            currency TEXT,
            fiat_base_multiplier INTEGER DEFAULT 1,
            served_meta INTEGER NOT NULL,
            served_pr INTEGER NOT NULL,
            webhook_url TEXT,
            success_text TEXT,
            success_url TEXT,
            comment_chars INTEGER DEFAULT 0,
            webhook_headers TEXT,
            webhook_body TEXT
            );
        """
    )

    for row in [
        list(row) for row in await db.fetchall("SELECT * FROM lnurlp.pay_links_old")
    ]:
        await db.execute(
            """
            INSERT INTO lnurlp.pay_links (
                id,
                wallet,
                description,
                min,
                served_meta,
                served_pr,
                webhook_url,
                success_text,
                success_url,
                currency,
                comment_chars,
                max,
                fiat_base_multiplier,
                webhook_headers,
                webhook_body
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row[0]),
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                row[10],
                row[11],
                row[12],
                row[13],
                row[14],
            ),
        )

    await db.execute("DROP TABLE lnurlp.pay_links_old")
