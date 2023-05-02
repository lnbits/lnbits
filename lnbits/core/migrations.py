import datetime

from loguru import logger
from sqlalchemy.exc import OperationalError

from lnbits import bolt11


async def m000_create_migrations_table(db):
    await db.execute(
        """
    CREATE TABLE IF NOT EXISTS dbversions (
        db TEXT PRIMARY KEY,
        version INT NOT NULL
    )
    """
    )


async def m001_initial(db):
    """
    Initial LNbits tables.
    """
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            email TEXT,
            pass TEXT
        );
    """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS extensions (
            "user" TEXT NOT NULL,
            extension TEXT NOT NULL,
            active BOOLEAN DEFAULT false,

            UNIQUE ("user", extension)
        );
    """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            "user" TEXT NOT NULL,
            adminkey TEXT NOT NULL,
            inkey TEXT
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS apipayments (
            payhash TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            fee INTEGER NOT NULL DEFAULT 0,
            wallet TEXT NOT NULL,
            pending BOOLEAN NOT NULL,
            memo TEXT,
            time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            UNIQUE (wallet, payhash)
        );
    """
    )

    await db.execute(
        """
        CREATE VIEW balances AS
        SELECT wallet, COALESCE(SUM(s), 0) AS balance FROM (
            SELECT wallet, SUM(amount) AS s  -- incoming
            FROM apipayments
            WHERE amount > 0 AND pending = false  -- don't sum pending
            GROUP BY wallet
            UNION ALL
            SELECT wallet, SUM(amount + fee) AS s  -- outgoing, sum fees
            FROM apipayments
            WHERE amount < 0  -- do sum pending
            GROUP BY wallet
        )x
        GROUP BY wallet;
    """
    )


async def m002_add_fields_to_apipayments(db):
    """
    Adding fields to apipayments for better accounting,
    and renaming payhash to checking_id since that is what it really is.
    """
    try:
        await db.execute("ALTER TABLE apipayments RENAME COLUMN payhash TO checking_id")
        await db.execute("ALTER TABLE apipayments ADD COLUMN hash TEXT")
        await db.execute("CREATE INDEX by_hash ON apipayments (hash)")
        await db.execute("ALTER TABLE apipayments ADD COLUMN preimage TEXT")
        await db.execute("ALTER TABLE apipayments ADD COLUMN bolt11 TEXT")
        await db.execute("ALTER TABLE apipayments ADD COLUMN extra TEXT")

        import json

        rows = await (await db.execute("SELECT * FROM apipayments")).fetchall()
        for row in rows:
            if not row["memo"] or not row["memo"].startswith("#"):
                continue

            for ext in ["withdraw", "events", "lnticket", "paywall", "tpos"]:
                prefix = f"#{ext} "
                if row["memo"].startswith(prefix):
                    new = row["memo"][len(prefix) :]
                    await db.execute(
                        """
                        UPDATE apipayments SET extra = ?, memo = ?
                        WHERE checking_id = ? AND memo = ?
                        """,
                        (
                            json.dumps({"tag": ext}),
                            new,
                            row["checking_id"],
                            row["memo"],
                        ),
                    )
                    break
    except OperationalError:
        # this is necessary now because it may be the case that this migration will
        # run twice in some environments.
        # catching errors like this won't be necessary in anymore now that we
        # keep track of db versions so no migration ever runs twice.
        pass


async def m003_add_invoice_webhook(db):
    """
    Special column for webhook endpoints that can be assigned
    to each different invoice.
    """

    await db.execute("ALTER TABLE apipayments ADD COLUMN webhook TEXT")
    await db.execute("ALTER TABLE apipayments ADD COLUMN webhook_status TEXT")


async def m004_ensure_fees_are_always_negative(db):
    """
    Use abs() so wallet backends don't have to care about the sign of the fees.
    """

    await db.execute("DROP VIEW balances")
    await db.execute(
        """
        CREATE VIEW balances AS
        SELECT wallet, COALESCE(SUM(s), 0) AS balance FROM (
            SELECT wallet, SUM(amount) AS s  -- incoming
            FROM apipayments
            WHERE amount > 0 AND pending = false  -- don't sum pending
            GROUP BY wallet
            UNION ALL
            SELECT wallet, SUM(amount - abs(fee)) AS s  -- outgoing, sum fees
            FROM apipayments
            WHERE amount < 0  -- do sum pending
            GROUP BY wallet
        )x
        GROUP BY wallet;
    """
    )


async def m005_balance_check_balance_notify(db):
    """
    Keep track of balanceCheck-enabled lnurl-withdrawals to be consumed by an LNbits wallet and of balanceNotify URLs supplied by users to empty their wallets.
    """

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS balance_check (
          wallet TEXT NOT NULL REFERENCES wallets (id),
          service TEXT NOT NULL,
          url TEXT NOT NULL,

          UNIQUE(wallet, service)
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS balance_notify (
          wallet TEXT NOT NULL REFERENCES wallets (id),
          url TEXT NOT NULL,

          UNIQUE(wallet, url)
        );
    """
    )


async def m006_add_invoice_expiry_to_apipayments(db):
    """
    Adds invoice expiry column to apipayments.
    """
    try:
        await db.execute("ALTER TABLE apipayments ADD COLUMN expiry TIMESTAMP")
    except OperationalError:
        pass


async def m007_set_invoice_expiries(db):
    """
    Precomputes invoice expiry for existing pending incoming payments.
    """
    try:
        rows = await (
            await db.execute(
                f"""
                SELECT bolt11, checking_id
                FROM apipayments
                WHERE pending = true
                AND amount > 0
                AND bolt11 IS NOT NULL
                AND expiry IS NULL
                AND time < {db.timestamp_now}
                """
            )
        ).fetchall()
        if len(rows):
            logger.info(f"Migration: Checking expiry of {len(rows)} invoices")
        for i, (
            payment_request,
            checking_id,
        ) in enumerate(rows):
            try:
                invoice = bolt11.decode(payment_request)
                if invoice.expiry is None:
                    continue

                expiration_date = datetime.datetime.fromtimestamp(
                    invoice.date + invoice.expiry
                )
                logger.info(
                    f"Migration: {i+1}/{len(rows)} setting expiry of invoice {invoice.payment_hash} to {expiration_date}"
                )
                await db.execute(
                    """
                    UPDATE apipayments SET expiry = ?
                    WHERE checking_id = ? AND amount > 0
                    """,
                    (
                        db.datetime_to_timestamp(expiration_date),
                        checking_id,
                    ),
                )
            except:
                continue
    except OperationalError:
        # this is necessary now because it may be the case that this migration will
        # run twice in some environments.
        # catching errors like this won't be necessary in anymore now that we
        # keep track of db versions so no migration ever runs twice.
        pass


async def m008_create_admin_settings_table(db):
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            super_user TEXT,
            editable_settings TEXT NOT NULL DEFAULT '{}'
        );
    """
    )


async def m009_create_tinyurl_table(db):
    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS tiny_url (
          id TEXT PRIMARY KEY,
          url TEXT,
          endless BOOL NOT NULL DEFAULT false,
          wallet TEXT,
          time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m010_create_installed_extensions_table(db):
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS installed_extensions (
            id TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            name TEXT NOT NULL,
            short_description TEXT,
            icon TEXT,
            stars INT NOT NULL DEFAULT 0,
            active BOOLEAN DEFAULT false,
            meta TEXT NOT NULL DEFAULT '{}'
        );
    """
    )
