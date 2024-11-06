from __future__ import annotations

from typing import Optional

from pydantic import Field

from .lnbits import LNbitsSettings


class WebPushSettings(LNbitsSettings):
    lnbits_webpush_pubkey: Optional[str] = Field(default=None)
    lnbits_webpush_privkey: Optional[str] = Field(default=None)
