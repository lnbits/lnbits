from __future__ import annotations

from typing import Optional

from pydantic import Field

from .lnbits import LNbitsSettings


class FeeSettings(LNbitsSettings):

    lnbits_reserve_fee_min: int = Field(default=2000)
    lnbits_reserve_fee_percent: float = Field(default=1.0)
    lnbits_service_fee: float = Field(default=0)
    lnbits_service_fee_ignore_internal: bool = Field(default=True)
    lnbits_service_fee_max: int = Field(default=0)
    lnbits_service_fee_wallet: Optional[str] = Field(default=None)

    # WARN: this same value must be used for balance check and passed to
    # funding_source.pay_invoice(), it may cause a vulnerability if the values differ
    def fee_reserve(self, amount_msat: int, internal: bool = False) -> int:
        if internal:
            return 0
        reserve_min = self.lnbits_reserve_fee_min
        reserve_percent = self.lnbits_reserve_fee_percent
        return max(int(reserve_min), int(amount_msat * reserve_percent / 100.0))
