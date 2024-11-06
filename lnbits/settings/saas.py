from __future__ import annotations

from typing import Optional

from pydantic import Field

from .lnbits import LNbitsSettings


class SaaSSettings(LNbitsSettings):
    lnbits_saas_callback: Optional[str] = Field(default=None)
    lnbits_saas_secret: Optional[str] = Field(default=None)
    lnbits_saas_instance_id: Optional[str] = Field(default=None)
