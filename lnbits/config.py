import importlib
import json
from os import getenv, path
from typing import List, Optional

from pydantic import BaseSettings, Field, validator

wallets_module = importlib.import_module("lnbits.wallets")
wallet_class = getattr(    
    wallets_module, getenv("LNBITS_BACKEND_WALLET_CLASS", "VoidWallet")
)

WALLET = wallet_class()

def list_parse_fallback(v):
    try:
        return json.loads(v)
    except Exception as e:
        return v.replace(' ','').split(',')

class Settings(BaseSettings):
    # users
    admin_users: List[str] = Field(default_factory=list, env="LNBITS_ADMIN_USERS")
    allowed_users: List[str] = Field(default_factory=list, env="LNBITS_ALLOWED_USERS")
    admin_ext: List[str] = Field(default_factory=list, env="LNBITS_ADMIN_EXTENSIONS")
    disabled_ext: List[str] = Field(default_factory=list, env="LNBITS_DISABLED_EXTENSIONS")
    funding_source: str = Field(default="VoidWallet", env="LNBITS_BACKEND_WALLET_CLASS")
    # ops
    data_folder: str = Field(default=None, env="LNBITS_DATA_FOLDER")
    database_url: str = Field(default=None, env="LNBITS_DATABASE_URL")
    force_https: bool = Field(default=True, env="LNBITS_FORCE_HTTPS")
    service_fee: float = Field(default=0, env="LNBITS_SERVICE_FEE")
    hide_api: bool = Field(default=False, env="LNBITS_HIDE_API")
    denomination: str = Field(default="sats", env="LNBITS_DENOMINATION")
    # Change theme
    site_title: str = Field(default="LNbits", env="LNBITS_SITE_TITLE")
    site_tagline: str = Field(default="free and open-source lightning wallet", env="LNBITS_SITE_TAGLINE")
    site_description: str = Field(default=None, env="LNBITS_SITE_DESCRIPTION")
    default_wallet_name: str = Field(default="LNbits wallet", env="LNBITS_DEFAULT_WALLET_NAME")
    theme: List[str] = Field(default="classic, flamingo, mint, salvador, monochrome, autumn", env="LNBITS_THEME_OPTIONS")
    ad_space: List[str] = Field(default_factory=list, env="LNBITS_AD_SPACE")
    # .env
    env: Optional[str]
    debug: Optional[str]
    host: Optional[str]
    port: Optional[str]
    lnbits_path: Optional[str] = path.dirname(path.realpath(__file__))  

    # @validator('admin_users', 'allowed_users', 'admin_ext', 'disabled_ext', pre=True)
    # def validate(cls, val):
    #     print(val)
    #     return val.split(',')

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        json_loads = list_parse_fallback


conf = Settings()
WALLET = wallet_class()
