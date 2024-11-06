from __future__ import annotations

from pydantic import Field

from .lnbits import LNbitsSettings


class SecuritySettings(LNbitsSettings):
    lnbits_rate_limit_no: str = Field(default="200")
    lnbits_rate_limit_unit: str = Field(default="minute")
    lnbits_allowed_ips: list[str] = Field(default=[])
    lnbits_blocked_ips: list[str] = Field(default=[])
    lnbits_notifications: bool = Field(default=False)
    lnbits_killswitch: bool = Field(default=False)
    lnbits_killswitch_interval: int = Field(default=60)
    lnbits_wallet_limit_max_balance: int = Field(default=0)
    lnbits_wallet_limit_daily_max_withdraw: int = Field(default=0)
    lnbits_wallet_limit_secs_between_trans: int = Field(default=0)
    lnbits_watchdog: bool = Field(default=False)
    lnbits_watchdog_interval: int = Field(default=60)
    lnbits_watchdog_delta: int = Field(default=1_000_000)
    lnbits_status_manifest: str = Field(
        default=(
            "https://raw.githubusercontent.com/lnbits/lnbits-status/main/manifest.json"
        )
    )

    def is_wallet_max_balance_exceeded(self, amount):
        return (
            self.lnbits_wallet_limit_max_balance
            and self.lnbits_wallet_limit_max_balance > 0
            and amount > self.lnbits_wallet_limit_max_balance
        )
