from os import getenv

from sqlalchemy.exc import OperationalError  # type: ignore

from lnbits.config import conf
from lnbits.helpers import urlsafe_short_hash


async def get_admin_user():
    if(conf.admin_users[0]):
        return conf.admin_users[0]
    from lnbits.core.crud import create_account, get_user
    print("Seems like there's no admin users yet. Let's create an account for you!")
    account = await create_account()
    user = account.id
    assert user, "Newly created user couldn't be retrieved"
    print(f"Your newly created account/user id is: {user}. This will be the Super Admin user.")
    conf.admin_users.insert(0, user)
    return user



async def m001_create_admin_table(db):
    # users/server
    user = await get_admin_user()
    admin_users = ",".join(conf.admin_users)
    allowed_users = ",".join(conf.allowed_users)
    admin_ext = ",".join(conf.admin_ext)
    disabled_ext = ",".join(conf.disabled_ext)
    funding_source = conf.funding_source
    #operational
    data_folder = conf.data_folder
    database_url = conf.database_url
    force_https = conf.force_https
    service_fee = conf.service_fee
    hide_api = conf.hide_api
    denomination = conf.denomination
    # Theme'ing
    site_title = conf.site_title
    site_tagline = conf.site_tagline
    site_description = conf.site_description
    default_wallet_name = conf.default_wallet_name
    theme = ",".join(conf.theme)
    custom_logo = conf.custom_logo
    ad_space = ",".join(conf.ad_space)

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin.admin (
            "user" TEXT PRIMARY KEY,
            admin_users TEXT,
            allowed_users TEXT,
            admin_ext TEXT,
            disabled_ext TEXT,
            funding_source TEXT,
            data_folder TEXT,
            database_url TEXT,
            force_https BOOLEAN,
            service_fee REAL,
            hide_api BOOLEAN,
            denomination TEXT,
            site_title TEXT,
            site_tagline TEXT,
            site_description TEXT,
            default_wallet_name TEXT,
            theme TEXT,
            custom_logo TEXT,
            ad_space TEXT
        );
    """
    )
    await db.execute(
        """
        INSERT INTO admin.admin (
            "user", 
            admin_users,
            allowed_users,
            admin_ext,
            disabled_ext,
            funding_source,
            data_folder,
            database_url,
            force_https,
            service_fee,
            hide_api,
            denomination,
            site_title,
            site_tagline,
            site_description,
            default_wallet_name,
            theme,
            custom_logo,
            ad_space)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user,
            admin_users,
            allowed_users,
            admin_ext,
            disabled_ext,
            funding_source,
            data_folder,
            database_url,
            force_https,
            service_fee,
            hide_api,
            denomination,
            site_title,
            site_tagline,
            site_description,
            default_wallet_name,
            theme,
            custom_logo,
            ad_space,
        ),
    )


async def m001_create_funding_table(db):

    funding_wallet = getenv("LNBITS_BACKEND_WALLET_CLASS")

    # Make the funding table,  if it does not already exist
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin.funding (
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, port, admin_key, cert, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, cert, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, cert, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, selected)
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
        INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, selected)
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
    #     INSERT INTO admin.funding (id, backend_wallet, endpoint, admin_key, selected)
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
