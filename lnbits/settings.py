import importlib
import importlib.metadata
import inspect
import json
import subprocess
from os import path
from sqlite3 import Row
from typing import Any, List, Optional

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
    @classmethod
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


class ExtensionsSettings(LNbitsSettings):
    lnbits_admin_extensions: List[str] = Field(default=[])
    lnbits_extensions_manifests: List[str] = Field(
        default=[
            "https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions.json"
        ]
    )


class ExtensionsInstallSettings(LNbitsSettings):
    lnbits_extensions_default_install: List[str] = Field(default=[])
    # required due to GitHUb rate-limit
    lnbits_ext_github_token: str = Field(default="")


class InstalledExtensionsSettings(LNbitsSettings):
    # installed extensions that have been deactivated
    lnbits_deactivated_extensions: List[str] = Field(default=[])
    # upgraded extensions that require API redirects
    lnbits_upgraded_extensions: List[str] = Field(default=[])
    # list of redirects that extensions want to perform
    lnbits_extensions_redirects: List[Any] = Field(default=[])


class ThemesSettings(LNbitsSettings):
    lnbits_site_title: str = Field(default="LNbits")
    lnbits_site_tagline: str = Field(default="free and open-source lightning wallet")
    lnbits_site_description: str = Field(default=None)
    lnbits_default_wallet_name: str = Field(default="LNbits wallet")
    lnbits_theme_options: List[str] = Field(
        default=[
            "classic",
            "freedom",
            "mint",
            "salvador",
            "monochrome",
            "autumn",
            "cyber",
        ]
    )
    lnbits_custom_logo: str = Field(default=None)
    lnbits_ad_space_title: str = Field(default="Supported by")
    lnbits_ad_space: str = Field(
        default="https://shop.lnbits.com/;/static/images/lnbits-shop-light.png;/static/images/lnbits-shop-dark.png"
    )  # sneaky sneaky
    lnbits_ad_space_enabled: bool = Field(default=False)
    lnbits_allowed_currencies: List[str] = Field(default=[])


class OpsSettings(LNbitsSettings):
    lnbits_baseurl: str = Field(default="http://127.0.0.1:5000/")
    lnbits_reserve_fee_min: int = Field(default=2000)
    lnbits_reserve_fee_percent: float = Field(default=1.0)
    lnbits_service_fee: float = Field(default=0)
    lnbits_hide_api: bool = Field(default=False)
    lnbits_denomination: str = Field(default="sats")


class SecuritySettings(LNbitsSettings):
    lnbits_rate_limit_no: str = Field(default="200")
    lnbits_rate_limit_unit: str = Field(default="minute")
    lnbits_allowed_ips: List[str] = Field(default=[])
    lnbits_blocked_ips: List[str] = Field(default=[])
    lnbits_notifications: bool = Field(default=False)
    lnbits_killswitch: bool = Field(default=False)
    lnbits_killswitch_interval: int = Field(default=60)
    lnbits_watchdog: bool = Field(default=False)
    lnbits_watchdog_interval: int = Field(default=60)
    lnbits_watchdog_delta: int = Field(default=1_000_000)
    lnbits_status_manifest: str = Field(
        default="https://raw.githubusercontent.com/lnbits/lnbits-status/main/manifest.json"
    )


class FakeWalletFundingSource(LNbitsSettings):
    fake_wallet_secret: str = Field(default="ToTheMoon1")


class LNbitsFundingSource(LNbitsSettings):
    lnbits_endpoint: str = Field(default="https://legend.lnbits.com")
    lnbits_key: Optional[str] = Field(default=None)
    lnbits_admin_key: Optional[str] = Field(default=None)
    lnbits_invoice_key: Optional[str] = Field(default=None)


class ClicheFundingSource(LNbitsSettings):
    cliche_endpoint: Optional[str] = Field(default=None)


class CoreLightningFundingSource(LNbitsSettings):
    corelightning_rpc: Optional[str] = Field(default=None)
    clightning_rpc: Optional[str] = Field(default=None)


class CLNRestFundingSource(LNbitsSettings):
    cln_rest_url: Optional[str] = Field(default=None)
    cln_rest_macaroon: Optional[str] = Field(default=None)
    cln_rest_cert: Optional[str] = Field(default=None)


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
    lnpay_admin_key: Optional[str] = Field(default=None)


class OpenNodeFundingSource(LNbitsSettings):
    opennode_api_endpoint: Optional[str] = Field(default=None)
    opennode_key: Optional[str] = Field(default=None)
    opennode_admin_key: Optional[str] = Field(default=None)
    opennode_invoice_key: Optional[str] = Field(default=None)


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


class LightningSettings(LNbitsSettings):
    lightning_invoice_expiry: int = Field(default=600)


class FundingSourcesSettings(
    FakeWalletFundingSource,
    LNbitsFundingSource,
    ClicheFundingSource,
    CoreLightningFundingSource,
    CLNRestFundingSource,
    EclairFundingSource,
    LndRestFundingSource,
    LndGrpcFundingSource,
    LnPayFundingSource,
    OpenNodeFundingSource,
    SparkFundingSource,
    LnTipsFundingSource,
):
    lnbits_backend_wallet_class: str = Field(default="VoidWallet")


class EditableSettings(
    UsersSettings,
    ExtensionsSettings,
    ThemesSettings,
    OpsSettings,
    SecuritySettings,
    FundingSourcesSettings,
    BoltzExtensionSettings,
    LightningSettings,
):
    @validator(
        "lnbits_admin_users",
        "lnbits_allowed_users",
        "lnbits_theme_options",
        "lnbits_admin_extensions",
        pre=True,
    )
    @classmethod
    def validate_editable_settings(cls, val):
        return super().validate(val)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            **{k: v for k, v in d.items() if k in inspect.signature(cls).parameters}
        )


class EnvSettings(LNbitsSettings):
    debug: bool = Field(default=False)
    bundle_assets: bool = Field(default=True)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5000)
    forwarded_allow_ips: str = Field(default="*")
    lnbits_path: str = Field(default=".")
    lnbits_commit: str = Field(default="unknown")
    super_user: str = Field(default="")
    version: str = Field(default="0.0.0")


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
            "CoreLightningWallet",
            "LndRestWallet",
            "EclairWallet",
            "LndWallet",
            "LnTipsWallet",
            "LNPayWallet",
            "LNbitsWallet",
            "OpenNodeWallet",
        ]
    )


class TransientSettings(InstalledExtensionsSettings):
    # Transient Settings:
    #  - are initialized, updated and used at runtime
    #  - are not read from a file or from the `settings` table
    #  - are not persisted in the `settings` table when the settings are updated
    #  - are cleared on server restart

    @classmethod
    def readonly_fields(cls):
        return [f for f in inspect.signature(cls).parameters if not f.startswith("_")]


class ReadOnlySettings(
    EnvSettings,
    ExtensionsInstallSettings,
    SaaSSettings,
    PersistenceSettings,
    SuperUserSettings,
):
    lnbits_admin_ui: bool = Field(default=False)

    @validator(
        "lnbits_allowed_funding_sources",
        pre=True,
    )
    @classmethod
    def validate_readonly_settings(cls, val):
        return super().validate(val)

    @classmethod
    def readonly_fields(cls):
        return [f for f in inspect.signature(cls).parameters if not f.startswith("_")]


class Settings(EditableSettings, ReadOnlySettings, TransientSettings):
    @classmethod
    def from_row(cls, row: Row) -> "Settings":
        data = dict(row)
        return cls(**data)


class SuperSettings(EditableSettings):
    super_user: str


class AdminSettings(EditableSettings):
    is_super_user: bool
    lnbits_allowed_funding_sources: Optional[List[str]]


def set_cli_settings(**kwargs):
    for key, value in kwargs.items():
        setattr(settings, key, value)


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


readonly_variables = ReadOnlySettings.readonly_fields()
transient_variables = TransientSettings.readonly_fields()

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

settings.version = importlib.metadata.version("lnbits")


def get_wallet_class():
    """
    Backwards compatibility
    """
    from lnbits.wallets import get_wallet_class

    return get_wallet_class()
