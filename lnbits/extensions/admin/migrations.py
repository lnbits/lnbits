from sqlalchemy.exc import OperationalError  # type: ignore
from os import getenv
from lnbits.helpers import urlsafe_short_hash


async def m001_create_admin_table(db):
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
    funding_source = ""

    if getenv("LNBITS_SITE_TITLE"):
        site_title = getenv("LNBITS_SITE_TITLE")

    if getenv("LNBITS_SITE_TAGLINE"):
        tagline = getenv("LNBITS_SITE_TAGLINE")

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

    if getenv("LNBITS_BACKEND_WALLET_CLASS"):
        funding_source = getenv("LNBITS_BACKEND_WALLET_CLASS")

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin (
            user TEXT,
            site_title TEXT,
            tagline TEXT,
            primary_color TEXT,
            secondary_color TEXT,
            allowed_users TEXT,
            default_wallet_name TEXT,
            data_folder TEXT,
            disabled_ext TEXT,
            force_https BOOLEAN,
            service_fee INT,
            funding_source TEXT
        );
    """
    )
    await db.execute(
        """
        INSERT INTO admin (user, site_title, tagline, primary_color, secondary_color, allowed_users, default_wallet_name, data_folder, disabled_ext, force_https, service_fee, funding_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            funding_source,
        ),
    )


async def m001_create_funding_table(db):

    # Make the funding table,  if it does not already exist

    await db.execute(
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
            balance int
        );
    """
    )

    # Get the funding source rows back if they exist

    CLightningWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("CLightningWallet",)
    )
    LnbitsWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("LnbitsWallet",)
    )
    LndWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("LndWallet",)
    )
    LndRestWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("LndRestWallet",)
    )
    LNPayWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("LNPayWallet",)
    )
    LntxbotWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("LntxbotWallet",)
    )
    OpenNodeWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("OpenNodeWallet",)
    )
    SparkWallet = await db.fetchall(
        "SELECT * FROM funding WHERE backend_wallet = ?", ("SparkWallet",)
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint)
        VALUES (?, ?, ?)
        """,
        (urlsafe_short_hash(), "CLightningWallet", getenv("CLIGHTNING_RPC")),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key)
        VALUES (?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "LnbitsWallet",
            getenv("LNBITS_ENDPOINT"),
            getenv("LNBITS_KEY"),
        ),
    )

    await db.execute(
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

    await db.execute(
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

    await db.execute(
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

    await db.execute(
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

    await db.execute(
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

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, invoice_key, admin_key)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "SparkWallet",
            getenv("SPARK_URL"),
            getenv("SPARK_INVOICE_KEY"),  # doesn't exist
            getenv("SPARK_TOKEN"),
        ),
    )
