from os import getenv

from sqlalchemy.exc import OperationalError  # type: ignore

from lnbits.helpers import urlsafe_short_hash


async def m001_create_admin_table(db):
    user = None
    site_title = None
    site_tagline = None
    site_description = None
    allowed_users = None
    admin_users = None
    default_wallet_name = None
    data_folder = None
    disabled_ext = None
    force_https = True
    service_fee = 0
    funding_source = ""

    if getenv("LNBITS_SITE_TITLE"):
        site_title = getenv("LNBITS_SITE_TITLE")

    if getenv("LNBITS_SITE_TAGLINE"):
        site_tagline = getenv("LNBITS_SITE_TAGLINE")

    if getenv("LNBITS_SITE_DESCRIPTION"):
        site_description = getenv("LNBITS_SITE_DESCRIPTION")

    if getenv("LNBITS_ALLOWED_USERS"):
        allowed_users = getenv("LNBITS_ALLOWED_USERS")

    if getenv("LNBITS_ADMIN_USERS"):
        admin_users = "".join(getenv("LNBITS_ADMIN_USERS").split())
        user = admin_users.split(',')[0]

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
            "user" TEXT,
            site_title TEXT,
            site_tagline TEXT,
            site_description TEXT,
            admin_users TEXT,
            allowed_users TEXT,
            default_wallet_name TEXT,
            data_folder TEXT,
            disabled_ext TEXT,
            force_https BOOLEAN,
            service_fee REAL,
            funding_source TEXT
        );
    """
    )
    await db.execute(
        """
        INSERT INTO admin ("user", site_title, site_tagline, site_description, admin_users, allowed_users, default_wallet_name, data_folder, disabled_ext, force_https, service_fee, funding_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.strip(),
            site_title,
            site_tagline,
            site_description,
            admin_users[1:],
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

    funding_wallet = getenv("LNBITS_BACKEND_WALLET_CLASS")

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
            balance INT,
            selected INT
        );
    """
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, selected)
        VALUES (?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "CLightningWallet",
            getenv("CLIGHTNING_RPC"),
            1 if funding_wallet == "CLightningWallet" else 0,
        ),
    )
    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key, selected)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "SparkWallet",
            getenv("SPARK_URL"),
            getenv("SPARK_TOKEN"),
            1 if funding_wallet == "SparkWallet" else 0,
        ),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key, selected)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "LnbitsWallet",
            getenv("LNBITS_ENDPOINT"),
            getenv("LNBITS_KEY"),
            1 if funding_wallet == "LnbitsWallet" else 0,
        ),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, port, admin_key, cert, selected)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "LndWallet",
            getenv("LND_GRPC_ENDPOINT"),
            getenv("LND_GRPC_PORT"),
            getenv("LND_GRPC_MACAROON"),
            getenv("LND_GRPC_CERT"),
            1 if funding_wallet == "LndWallet" else 0,
        ),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key, cert, selected)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "LndRestWallet",
            getenv("LND_REST_ENDPOINT"),
            getenv("LND_REST_MACAROON"),
            getenv("LND_REST_CERT"),
            1 if funding_wallet == "LndWallet" else 0,
        ),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key, cert, selected)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "LNPayWallet",
            getenv("LNPAY_API_ENDPOINT"),
            getenv("LNPAY_WALLET_KEY"),
            getenv("LNPAY_API_KEY"),  # this is going in as the cert
            1 if funding_wallet == "LNPayWallet" else 0,
        ),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key, selected)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "LntxbotWallet",
            getenv("LNTXBOT_API_ENDPOINT"),
            getenv("LNTXBOT_KEY"),
            1 if funding_wallet == "LntxbotWallet" else 0,
        ),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key, selected)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "OpenNodeWallet",
            getenv("OPENNODE_API_ENDPOINT"),
            getenv("OPENNODE_KEY"),
            1 if funding_wallet == "OpenNodeWallet" else 0,
        ),
    )

    await db.execute(
        """
        INSERT INTO funding (id, backend_wallet, endpoint, admin_key, selected)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            "SparkWallet",
            getenv("SPARK_URL"),
            getenv("SPARK_TOKEN"),
            1 if funding_wallet == "SparkWallet" else 0,
        ),
    )

    ## PLACEHOLDER FOR ECLAIR WALLET
    # await db.execute(
    #     """
    #     INSERT INTO funding (id, backend_wallet, endpoint, admin_key, selected)
    #     VALUES (?, ?, ?, ?, ?)
    #     """,
    #     (
    #         urlsafe_short_hash(),
    #         "EclairWallet",
    #         getenv("ECLAIR_URL"),
    #         getenv("ECLAIR_PASS"),
    #         1 if funding_wallet == "EclairWallet" else 0,
    #     ),
    # )
