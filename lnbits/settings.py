import importlib
import json
import subprocess
from os import path
from sqlite3 import Row
from typing import List, Optional

import httpx
from loguru import logger
from pydantic import BaseSettings, Field, validator


def list_parse_fallback(v):
    try:
        return json.loads(v)
    except Exception:
        replaced = v.replace(" ", "")
        if replaced:
            return replaced.split(",")
        else:
            return []


readonly_variables = [
    "host",
    "port",
    "debug",
    "lnbits_allowed_funding_sources",
    "lnbits_admin_extensions",
    "lnbits_saas_secret",
    "lnbits_saas_callback",
    "lnbits_saas_instance_id",
    "lnbits_admin_ui",
    "lnbits_commit",
    "lnbits_path",
    "forwarded_allow_ips",
]


class Settings(BaseSettings):

    lnbits_admin_ui: bool = Field(default=False)

    # .env
    debug: bool = Field(default=False)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5000)
    forwarded_allow_ips: str = Field(default="*")
    lnbits_path: str = Field(default=".")
    lnbits_commit: str = Field(default="unknown")
    super_user: str = Field(default="")

    # saas
    lnbits_saas_callback: Optional[str] = Field(default=None)
    lnbits_saas_secret: Optional[str] = Field(default=None)
    lnbits_saas_instance_id: Optional[str] = Field(default=None)

    # users
    lnbits_admin_users: List[str] = Field(default=[])
    lnbits_allowed_users: List[str] = Field(default=[])
    lnbits_admin_extensions: List[str] = Field(default=[])
    lnbits_disabled_extensions: List[str] = Field(default=[])

    # Change theme
    lnbits_site_title: str = Field(default="LNbits")
    lnbits_site_tagline: str = Field(default="free and open-source lightning wallet")
    lnbits_site_description: str = Field(default=None)
    lnbits_default_wallet_name: str = Field(default="LNbits wallet")
    lnbits_theme_options: List[str] = Field(
        default=["classic", "flamingo", "mint", "salvador", "monochrome", "autumn"]
    )
    lnbits_custom_logo: str = Field(default=None)
    lnbits_ad_space_title: str = Field(default="Suported by")
    lnbits_ad_space: str = Field(
        default="https://shop.lnbits.com/;/static/images/lnbits-shop-light.png;/static/images/lnbits-shop-dark.png"
    )  # sneaky sneaky
    lnbits_ad_space_enabled: bool = Field(default=False)

    # ops
    lnbits_data_folder: str = Field(default="./data")
    lnbits_database_url: str = Field(default=None)
    lnbits_force_https: bool = Field(default=False)
    lnbits_reserve_fee_min: int = Field(default=4000)
    lnbits_reserve_fee_percent: float = Field(default=1.0)
    lnbits_service_fee: float = Field(default=0)
    lnbits_hide_api: bool = Field(default=False)
    lnbits_denomination: str = Field(default="sats")

    # funding sources
    lnbits_backend_wallet_class: str = Field(default="VoidWallet")
    lnbits_allowed_funding_sources: List[str] = Field(
        default=[
            "VoidWallet",
            "FakeWallet",
            "CLightningWallet",
            "LndRestWallet",
            "LndWallet",
            "LntxbotWallet",
            "LNPayWallet",
            "LNbitsWallet",
            "OpenNodeWallet",
            "LnTipsWallet",
        ]
    )
    fake_wallet_secret: str = Field(default="ToTheMoon1")
    lnbits_endpoint: str = Field(default="https://legend.lnbits.com")
    lnbits_key: Optional[str] = Field(default=None)
    cliche_endpoint: Optional[str] = Field(default=None)
    corelightning_rpc: Optional[str] = Field(default=None)
    eclair_url: Optional[str] = Field(default=None)
    eclair_pass: Optional[str] = Field(default=None)
    lnd_rest_endpoint: Optional[str] = Field(default=None)
    lnd_rest_cert: Optional[str] = Field(default=None)
    lnd_rest_macaroon: Optional[str] = Field(default=None)
    lnd_rest_macaroon_encrypted: Optional[str] = Field(default=None)
    lnd_cert: Optional[str] = Field(default=None)
    lnd_admin_macaroon: Optional[str] = Field(default=None)
    lnd_invoice_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_endpoint: Optional[str] = Field(default=None)
    lnd_grpc_cert: Optional[str] = Field(default=None)
    lnd_grpc_port: Optional[int] = Field(default=None)
    lnd_grpc_admin_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_invoice_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_macaroon_encrypted: Optional[str] = Field(default=None)
    lnpay_api_endpoint: Optional[str] = Field(default=None)
    lnpay_api_key: Optional[str] = Field(default=None)
    lnpay_wallet_key: Optional[str] = Field(default=None)
    lntxbot_api_endpoint: Optional[str] = Field(default=None)
    lntxbot_key: Optional[str] = Field(default=None)
    opennode_api_endpoint: Optional[str] = Field(default=None)
    opennode_key: Optional[str] = Field(default=None)
    spark_url: Optional[str] = Field(default=None)
    spark_token: Optional[str] = Field(default=None)
    lntips_api_endpoint: Optional[str] = Field(default=None)
    lntips_api_key: Optional[str] = Field(default=None)
    lntips_admin_key: Optional[str] = Field(default=None)
    lntips_invoice_key: Optional[str] = Field(default=None)

    # boltz
    boltz_network: str = Field(default="main")
    boltz_url: str = Field(default="https://boltz.exchange/api")
    boltz_mempool_space_url: str = Field(default="https://mempool.space")
    boltz_mempool_space_url_ws: str = Field(default="wss://mempool.space")

    @validator(
        "lnbits_admin_users",
        "lnbits_allowed_users",
        "lnbits_theme_options",
        "lnbits_admin_extensions",
        "lnbits_disabled_extensions",
        "lnbits_allowed_funding_sources",
        pre=True,
    )
    def validate(cls, val):
        if type(val) == str:
            val = val.split(",") if val else []
        return val

    @classmethod
    def from_row(cls, row: Row) -> "Settings":
        data = dict(row)
        return cls(**data)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        json_loads = list_parse_fallback


settings = Settings()

settings.lnbits_path = str(path.dirname(path.realpath(__file__)))

try:
    settings.lnbits_commit = (
        subprocess.check_output(
            ["git", "-C", settings.lnbits_path, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        .strip()
        .decode("ascii")
    )
except:
    settings.lnbits_commit = "docker"


# printing enviroment variable for debugging
if not settings.lnbits_admin_ui:
    logger.debug(f"Enviroment Settings:")
    for key, value in settings.dict(exclude_none=True).items():
        logger.debug(f"{key}: {value}")


def set_cli_settings(**kwargs):
    for key, value in kwargs.items():
        setattr(settings, key, value)


async def check_admin_settings():
    if settings.lnbits_admin_ui:
        ext_db = importlib.import_module(f"lnbits.extensions.admin").db
        async with ext_db.connect() as db:
            row = await db.fetchone("SELECT * FROM admin.settings")

            # create new settings if table is empty
            if not row or len(row) == 0:
                logger.warning(
                    "admin.settings empty. inserting new settings and creating admin account"
                )
                row = await create_admin_settings(db)

            # setting settings from database into memory
            from lnbits.extensions.admin.models import AdminSettings

            sets = AdminSettings(
                **row,
                lnbits_allowed_funding_sources=settings.lnbits_allowed_funding_sources,
            )
            for key, value in sets.dict().items():
                if not key in readonly_variables:
                    try:
                        setattr(settings, key, value)
                    except:
                        logger.error(f"error overriding setting: {key}, value: {value}")

            # printing settings for debugging
            logger.debug(f"Admin settings:")
            for key, value in settings.dict(exclude_none=True).items():
                logger.debug(f"{key}: {value}")

            http = "https" if settings.lnbits_force_https else "http"
            admin_url = f"{http}://{settings.host}:{settings.port}/wallet?usr={settings.super_user}"
            logger.success(f"✔️ Access admin user account at: {admin_url}")

            # callback for saas
            if (
                settings.lnbits_saas_callback
                and settings.lnbits_saas_secret
                and settings.lnbits_saas_instance_id
            ):
                send_admin_user_to_saas()


wallets_module = importlib.import_module("lnbits.wallets")
FAKE_WALLET = getattr(wallets_module, "FakeWallet")()


def get_wallet_class():
    wallet_class = getattr(wallets_module, settings.lnbits_backend_wallet_class)
    return wallet_class()


async def create_admin_settings(db):

    # if not imported here, circular import error
    from lnbits.core.crud import create_account

    account = await create_account()
    settings.super_user = account.id
    keys = []
    values = ""
    for key, value in settings.dict(exclude_none=True).items():
        if not key in readonly_variables:
            keys.append(key)
            if type(value) == list:
                joined = ",".join(value)
                values += f"'{joined}'"
            if type(value) == int or type(value) == float:
                values += str(value)
            if type(value) == bool:
                values += "true" if value else "false"
            if type(value) == str:
                value = value.replace("'", "")
                values += f"'{value}'"
            values += ","
    q = ", ".join(keys)
    v = values.rstrip(",")
    sql = f"INSERT INTO admin.settings ({q}) VALUES ({v})"
    await db.execute(sql)
    logger.warning("initialized admin.settings from enviroment variables.")
    row = await db.fetchone("SELECT * FROM admin.settings")
    assert row, "Newly updated settings couldn't be retrieved"
    return row


def send_admin_user_to_saas():
    if settings.lnbits_saas_callback:
        with httpx.Client() as client:
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "X-API-KEY": settings.lnbits_saas_secret,
            }
            payload = {
                "instance_id": settings.lnbits_saas_instance_id,
                "adminuser": settings.super_user,
            }
            try:
                client.post(
                    settings.lnbits_saas_callback,
                    headers=headers,
                    json=payload,
                )
                logger.success("sent admin user to saas application")
            except:
                logger.error(
                    f"error sending admin user to saas: {settings.lnbits_saas_callback}"
                )
