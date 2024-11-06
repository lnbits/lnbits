from __future__ import annotations

from time import time

from pydantic import Field

from .lnbits import LNbitsSettings


class EnvSettings(LNbitsSettings):
    debug: bool = Field(default=False)
    debug_database: bool = Field(default=False)
    bundle_assets: bool = Field(default=True)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5000)
    forwarded_allow_ips: str = Field(default="*")
    lnbits_title: str = Field(default="LNbits API")
    lnbits_path: str = Field(default=".")
    lnbits_extensions_path: str = Field(default="lnbits")
    super_user: str = Field(default="")
    auth_secret_key: str = Field(default="")
    version: str = Field(default="0.0.0")
    user_agent: str = Field(default="")
    enable_log_to_file: bool = Field(default=True)
    log_rotation: str = Field(default="100 MB")
    log_retention: str = Field(default="3 months")
    server_startup_time: int = Field(default=time())
    cleanup_wallets_days: int = Field(default=90)
    funding_source_max_retries: int = Field(default=4)

    @property
    def has_default_extension_path(self) -> bool:
        return self.lnbits_extensions_path == "lnbits"
