import importlib
import inspect
import json
import subprocess
from os import path
from sqlite3 import Row
from typing import List, Optional

import httpx
from loguru import logger
from pydantic import BaseSettings, Extra, Field, validator


def list_parse_fallback(v):
    try:
        return json.loads(v)
    except Exception:
        replaced = v.replace(" ", "")
        if replaced:
            return replaced.split(",")
        else:
            return []


class LNbitsSettings(BaseSettings):
    def validate(cls, val):
        if type(val) == str:
            val = val.split(",") if val else []
        return val

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        json_loads = list_parse_fallback
        extra = Extra.ignore


class UsersSettings(LNbitsSettings):
    lnbits_admin_users: List[str] = Field(default=[])
    lnbits_allowed_users: List[str] = Field(default=[])
    lnbits_admin_extensions: List[str] = Field(default=[])
    lnbits_disabled_extensions: List[str] = Field(default=[])


class ThemesSettings(LNbitsSettings):
    lnbits_site_title: str = Field(default="LNbits")
    lnbits_site_tagline: str = Field(default="free and open-source lightning wallet")
    lnbits_site_description: str = Field(default=None)
    lnbits_default_wallet_name: str = Field(default="LNbits wallet")
    lnbits_theme_options: List[str] = Field(
        default=["classic", "flamingo", "mint", "salvador", "monochrome", "autumn"]
    )
    lnbits_custom_logo: str = Field(default=None)
    lnbits_ad_space_title: str = Field(default="Supported by")
    lnbits_ad_space: str = Field(
        default="https://shop.lnbits.com/;/static/images/lnbits-shop-light.png;/static/images/lnbits-shop-dark.png"
    )  # sneaky sneaky
    lnbits_ad_space_enabled: bool = Field(default=False)


class OpsSettings(LNbitsSettings):
    lnbits_force_https: bool = Field(default=False)
    lnbits_reserve_fee_min: int = Field(default=2000)
    lnbits_reserve_fee_percent: float = Field(default=1.0)
    lnbits_service_fee: float = Field(default=0)
    lnbits_hide_api: bool = Field(default=False)
    lnbits_denomination: str = Field(default="sats")


class FakeWalletFundingSource(LNbitsSettings):
    fake_wallet_secret: str = Field(default="ToTheMoon1")


class LNbitsFundingSource(LNbitsSettings):
    lnbits_endpoint: str = Field(default="https://legend.lnbits.com")
    lnbits_key: Optional[str] = Field(default=None)


class ClicheFundingSource(LNbitsSettings):
    cliche_endpoint: Optional[str] = Field(default=None)


class CoreLightningFundingSource(LNbitsSettings):
    corelightning_rpc: Optional[str] = Field(default=None)
    clightning_rpc: Optional[str] = Field(default=None)


class EclairFundingSource(LNbitsSettings):
    eclair_url: Optional[str] = Field(default=None)
    eclair_pass: Optional[str] = Field(default=None)


class LndRestFundingSource(LNbitsSettings):
    lnd_rest_endpoint: Optional[str] = Field(default=None)
    lnd_rest_cert: Optional[str] = Field(default=None)
    lnd_rest_macaroon: Optional[str] = Field(default=None)
    lnd_rest_macaroon_encrypted: Optional[str] = Field(default=None)
    lnd_cert: Optional[str] = Field(default=None)
    lnd_admin_macaroon: Optional[str] = Field(default=None)
    lnd_invoice_macaroon: Optional[str] = Field(default=None)
    lnd_rest_admin_macaroon: Optional[str] = Field(default=None)
    lnd_rest_invoice_macaroon: Optional[str] = Field(default=None)


class LndGrpcFundingSource(LNbitsSettings):
    lnd_grpc_endpoint: Optional[str] = Field(default=None)
    lnd_grpc_cert: Optional[str] = Field(default=None)
    lnd_grpc_port: Optional[int] = Field(default=None)
    lnd_grpc_admin_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_invoice_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_macaroon_encrypted: Optional[str] = Field(default=None)


class LnPayFundingSource(LNbitsSettings):
    lnpay_api_endpoint: Optional[str] = Field(default=None)
    lnpay_api_key: Optional[str] = Field(default=None)
    lnpay_wallet_key: Optional[str] = Field(default=None)


class LnTxtBotFundingSource(LNbitsSettings):
    lntxbot_api_endpoint: Optional[str] = Field(default=None)
    lntxbot_key: Optional[str] = Field(default=None)


class OpenNodeFundingSource(LNbitsSettings):
    opennode_api_endpoint: Optional[str] = Field(default=None)
    opennode_key: Optional[str] = Field(default=None)


class SparkFundingSource(LNbitsSettings):
    spark_url: Optional[str] = Field(default=None)
    spark_token: Optional[str] = Field(default=None)


class LnTipsFundingSource(LNbitsSettings):
    lntips_api_endpoint: Optional[str] = Field(default=None)
    lntips_api_key: Optional[str] = Field(default=None)
    lntips_admin_key: Optional[str] = Field(default=None)
    lntips_invoice_key: Optional[str] = Field(default=None)


# todo: must be extracted
class BoltzExtensionSettings(LNbitsSettings):
    boltz_network: str = Field(default="main")
    boltz_url: str = Field(default="https://boltz.exchange/api")
    boltz_mempool_space_url: str = Field(default="https://mempool.space")
    boltz_mempool_space_url_ws: str = Field(default="wss://mempool.space")


class FundingSourcesSettings(
    FakeWalletFundingSource,
    LNbitsFundingSource,
    ClicheFundingSource,
    CoreLightningFundingSource,
    EclairFundingSource,
    LndRestFundingSource,
    LndGrpcFundingSource,
    LnPayFundingSource,
    LnTxtBotFundingSource,
    OpenNodeFundingSource,
    SparkFundingSource,
    LnTipsFundingSource,
):
    lnbits_backend_wallet_class: str = Field(default="VoidWallet")


class EditableSettings(
    UsersSettings,
    ThemesSettings,
    OpsSettings,
    FundingSourcesSettings,
    BoltzExtensionSettings,
):
    @validator(
        "lnbits_admin_users",
        "lnbits_allowed_users",
        "lnbits_theme_options",
        "lnbits_admin_extensions",
        "lnbits_disabled_extensions",
        pre=True,
    )
    def validate_editable_settings(cls, val):
        return super().validate(cls, val)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            **{k: v for k, v in d.items() if k in inspect.signature(cls).parameters}
        )


class EnvSettings(LNbitsSettings):
    debug: bool = Field(default=False)
    file_log: bool = Field(default=False)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5000)
    forwarded_allow_ips: str = Field(default="*")
    lnbits_path: str = Field(default=".")
    lnbits_commit: str = Field(default="unknown")
    super_user: str = Field(default="")


class SaaSSettings(LNbitsSettings):
    lnbits_saas_callback: Optional[str] = Field(default=None)
    lnbits_saas_secret: Optional[str] = Field(default=None)
    lnbits_saas_instance_id: Optional[str] = Field(default=None)


class PersistenceSettings(LNbitsSettings):
    lnbits_data_folder: str = Field(default="./data")
    lnbits_database_url: str = Field(default=None)


class SuperUserSettings(LNbitsSettings):
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


class ReadOnlySettings(
    EnvSettings, SaaSSettings, PersistenceSettings, SuperUserSettings
):
    lnbits_admin_ui: bool = Field(default=False)

    @validator(
        "lnbits_allowed_funding_sources",
        pre=True,
    )
    def validate_readonly_settings(cls, val):
        return super().validate(cls, val)

    @classmethod
    def readonly_fields(cls):
        return [f for f in inspect.signature(cls).parameters if not f.startswith("_")]


class Settings(EditableSettings, ReadOnlySettings):
    @classmethod
    def from_row(cls, row: Row) -> "Settings":
        data = dict(row)
        return cls(**data)


class SuperSettings(EditableSettings):
    super_user: str


class AdminSettings(EditableSettings):
    super_user: bool
    lnbits_allowed_funding_sources: Optional[List[str]]


def set_cli_settings(**kwargs):
    for key, value in kwargs.items():
        setattr(settings, key, value)


# set wallet class after settings are loaded
def set_wallet_class():
    wallet_class = getattr(wallets_module, settings.lnbits_backend_wallet_class)
    global WALLET
    WALLET = wallet_class()


def get_wallet_class():
    # wallet_class = getattr(wallets_module, settings.lnbits_backend_wallet_class)
    return WALLET


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
                logger.success("sent super_user to saas application")
            except Exception as e:
                logger.error(
                    f"error sending super_user to saas: {settings.lnbits_saas_callback}. Error: {str(e)}"
                )


############### INIT #################

readonly_variables = ReadOnlySettings.readonly_fields()

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


wallets_module = importlib.import_module("lnbits.wallets")
FAKE_WALLET = getattr(wallets_module, "FakeWallet")()

# initialize as fake wallet
WALLET = FAKE_WALLET
