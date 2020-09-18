import sqlite3
from os import getenv
from lnbits.helpers import urlsafe_short_hash
from .crud import create_account, get_user


def m000_create_migrations_table(db):
    db.execute(
        """
    CREATE TABLE dbversions (
        db TEXT PRIMARY KEY,
        version INT NOT NULL
    )
    """
    )


def m001_initial(db):
    """
    Initial LNbits tables.
    """

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            email TEXT,
            pass TEXT
        );
    """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS extensions (
            user TEXT NOT NULL,
            extension TEXT NOT NULL,
            active BOOLEAN DEFAULT 0,

            UNIQUE (user, extension)
        );
    """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            user TEXT NOT NULL,
            adminkey TEXT NOT NULL,
            inkey TEXT
        );
    """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS apipayments (
            payhash TEXT NOT NULL,
            amount INTEGER NOT NULL,
            fee INTEGER NOT NULL DEFAULT 0,
            wallet TEXT NOT NULL,
            pending BOOLEAN NOT NULL,
            memo TEXT,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now')),

            UNIQUE (wallet, payhash)
        );
    """
    )

    db.execute(
        """
        CREATE VIEW IF NOT EXISTS balances AS
        SELECT wallet, COALESCE(SUM(s), 0) AS balance FROM (
            SELECT wallet, SUM(amount) AS s  -- incoming
            FROM apipayments
            WHERE amount > 0 AND pending = 0  -- don't sum pending
            GROUP BY wallet
            UNION ALL
            SELECT wallet, SUM(amount + fee) AS s  -- outgoing, sum fees
            FROM apipayments
            WHERE amount < 0  -- do sum pending
            GROUP BY wallet
        )
        GROUP BY wallet;
    """
    )


def m002_add_fields_to_apipayments(db):
    """
    Adding fields to apipayments for better accounting,
    and renaming payhash to checking_id since that is what it really is.
    """
    try:
        db.execute("ALTER TABLE apipayments RENAME COLUMN payhash TO checking_id")
        db.execute("ALTER TABLE apipayments ADD COLUMN hash TEXT")
        db.execute("CREATE INDEX by_hash ON apipayments (hash)")
        db.execute("ALTER TABLE apipayments ADD COLUMN preimage TEXT")
        db.execute("ALTER TABLE apipayments ADD COLUMN bolt11 TEXT")
        db.execute("ALTER TABLE apipayments ADD COLUMN extra TEXT")

        import json

        rows = db.fetchall("SELECT * FROM apipayments")
        for row in rows:
            if not row["memo"] or not row["memo"].startswith("#"):
                continue

            for ext in ["withdraw", "events", "lnticket", "paywall", "tpos"]:
                prefix = "#" + ext + " "
                if row["memo"].startswith(prefix):
                    new = row["memo"][len(prefix) :]
                    db.execute(
                        """
                        UPDATE apipayments SET extra = ?, memo = ?
                        WHERE checking_id = ? AND memo = ?
                        """,
                        (json.dumps({"tag": ext}), new, row["checking_id"], row["memo"]),
                    )
                    break
    except sqlite3.OperationalError:
        # this is necessary now because it may be the case that this migration will
        # run twice in some environments.
        # catching errors like this won't be necessary in anymore now that we
        # keep track of db versions so no migration ever runs twice.
        pass


def m003_create_admin_table(db):
    user = None
    site_title = None
    tagline = ""
    primary_color = "#673ab7"
    secondary_color = "#9c27b0"
    allowed_users = None
    default_wallet_name = None
    data_folder = None
    disabled_ext = None
    force_https = True
    service_fee = 0

    if getenv("LNBITS_SITE_TITLE"):
        site_title = getenv("LNBITS_SITE_TITLE")

    if getenv("LNBITS_ALLOWED_USERS"):
        allowed_users = getenv("LNBITS_ALLOWED_USERS")

    if getenv("LNBITS_DEFAULT_WALLET_NAME"):
        default_wallet_name = getenv("LNBITS_DEFAULT_WALLET_NAME")

    if getenv("LNBITS_DATA_FOLDER"):
        data_folder = getenv("LNBITS_DATA_FOLDER")

    if getenv("LNBITS_DISABLED_EXTENSIONS"):
        disabled_ext = getenv("LNBITS_DISABLED_EXTENSIONS")

    if getenv("LNBITS_FORCE_HTTPS"):
        force_https = getenv("LNBITS_FORCE_HTTPS")

    if getenv("LNBITS_SERVICE_FEE"):
        service_fee = getenv("LNBITS_SERVICE_FEE")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin (
            user TEXT,
            site_title TEXT NOT NULL,
            tagline TEXT,
            primary_color TEXT NOT NULL,
            secondary_color TEXT NOT NULL,
            allowed_users TEXT,
            default_wallet_name TEXT,
            data_folder TEXT,
            disabled_ext TEXT,
            force_https BOOLEAN NOT NULL,
            service_fee INT NOT NULL
        );
    """
    )
    db.execute(
        """
        INSERT INTO admin (user, site_title, tagline, primary_color, secondary_color, allowed_users, default_wallet_name, data_folder, disabled_ext, force_https, service_fee)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user,
            site_title,
            tagline,
            primary_color,
            secondary_color,
            allowed_users,
            default_wallet_name,
            data_folder,
            disabled_ext,
            force_https,
            service_fee,
        ),
    )


def m003_create_funding_table(db):

    # Make the funding table,  if it does not already exist

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS funding (
            id TEXT PRIMARY KEY,
            backend_wallet TEXT,
            endpoint TEXT,
            port INT,
            read_key TEXT,
            invoice_key TEXT,
            admin_key TEXT,
            cert TEXT,
            active BOOLEAN DEFAULT 0,
            balance int
        );
    """
    )

    # Get the funding source rows back if they exist

    CLightningWallet = db.fetchall("SELECT * FROM funding WHERE backend_wallet = ?", ("CLightningWallet",))
    LnbitsWallet = db.fetchall("SELECT * FROM funding WHERE backend_wallet = ?", ("LnbitsWallet",))
    LndWallet = db.fetchall("SELECT * FROM funding WHERE backend_wallet = ?", ("LndWallet",))
    LndRestWallet = db.fetchall("SELECT * FROM funding WHERE backend_wallet = ?", ("LndRestWallet",))
    LNPayWallet = db.fetchall("SELECT * FROM funding WHERE backend_wallet = ?", ("LNPayWallet",))
    LntxbotWallet = db.fetchall("SELECT * FROM funding WHERE backend_wallet = ?", ("LntxbotWallet",))
    OpenNodeWallet = db.fetchall("SELECT * FROM funding WHERE backend_wallet = ?", ("OpenNodeWallet",))

    # If the funding source rows do not exist and there is data in env for them, return the data and put it in a row

    if getenv("CLIGHTNING_RPC") and CLightningWallet != None:
        db.execute(
            """
            INSERT INTO funding (id, backend_wallet, endpoint)
            VALUES (?, ?, ?)
            """,
            (urlsafe_short_hash(), "CLightningWallet", getenv("CLIGHTNING_RPC")),
        )
    if getenv("LNBITS_INVOICE_MACAROON") and LnbitsWallet != None:
        db.execute(
            """
            INSERT INTO funding (id, backend_wallet, endpoint, invoice_key, admin_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                urlsafe_short_hash(),
                "LnbitsWallet",
                getenv("LNBITS_ENDPOINT"),
                getenv("LNBITS_INVOICE_MACAROON"),
                getenv("LNBITS_ADMIN_MACAROON"),
            ),
        )
    if getenv("LND_GRPC_ENDPOINT") and LndWallet != None:
        db.execute(
            """
            INSERT INTO funding (id, backend_wallet, endpoint, port, read_key, invoice_key, admin_key, cert)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                urlsafe_short_hash(),
                "LndWallet",
                getenv("LND_GRPC_ENDPOINT"),
                getenv("LND_GRPC_PORT"),
                getenv("LND_READ_MACAROON"),
                getenv("LND_INVOICE_MACAROON"),
                getenv("LND_ADMIN_MACAROON"),
                getenv("LND_CERT"),
            ),
        )

    if getenv("LND_REST_ENDPOINT") and LndRestWallet != None:
        db.execute(
            """
            INSERT INTO funding (id, backend_wallet, endpoint, read_key, invoice_key, admin_key, cert)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                urlsafe_short_hash(),
                "LndRestWallet",
                getenv("LND_REST_ENDPOINT"),
                getenv("LND_REST_READ_MACAROON"),
                getenv("LND_REST_INVOICE_MACAROON"),
                getenv("LND_REST_ADMIN_MACAROON"),
                getenv("LND_REST_CERT"),
            ),
        )

    if getenv("LNPAY_INVOICE_KEY") and LNPayWallet != None:
        db.execute(
            """
            INSERT INTO funding (id, backend_wallet, endpoint, read_key, invoice_key, admin_key, cert)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                urlsafe_short_hash(),
                "LNPayWallet",
                getenv("LNPAY_API_ENDPOINT"),
                getenv("LNPAY_READ_KEY"),
                getenv("LNPAY_INVOICE_KEY"),
                getenv("LNPAY_ADMIN_KEY"),
                getenv("LNPAY_API_KEY"),
            ),
        )

    if getenv("LNTXBOT_INVOICE_KEY") and LntxbotWallet != None:
        db.execute(
            """
            INSERT INTO funding (id, backend_wallet, endpoint, invoice_key, admin_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                urlsafe_short_hash(),
                "LntxbotWallet",
                getenv("LNTXBOT_API_ENDPOINT"),
                getenv("LNTXBOT_INVOICE_KEY"),
                getenv("LNTXBOT_ADMIN_KEY"),
            ),
        )

    if getenv("OPENNODE_INVOICE_KEY") and OpenNodeWallet != None:
        db.execute(
            """
            INSERT INTO funding (id, backend_wallet, endpoint, invoice_key, admin_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                urlsafe_short_hash(),
                "OpenNodeWallet",
                getenv("OPENNODE_API_ENDPOINT"),
                getenv("OPENNODE_INVOICE_KEY"),
                getenv("OPENNODE_ADMIN_KEY"),
            ),
        )

    if getenv("LNBITS_BACKEND_WALLET_CLASS"):
        db.execute(
            """
            UPDATE funding
            SET active = ?
            WHERE backend_wallet = ?
            """,
            (1, getenv("LNBITS_BACKEND_WALLET_CLASS")),
        )
