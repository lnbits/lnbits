from __future__ import annotations

from pydantic import Field

from .lnbits import LNbitsSettings


class OpsSettings(LNbitsSettings):
    lnbits_baseurl: str = Field(default="http://127.0.0.1:5000/")
    lnbits_hide_api: bool = Field(default=False)
    lnbits_denomination: str = Field(default="sats")
