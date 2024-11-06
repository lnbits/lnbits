from __future__ import annotations

from pydantic import Field

from .lnbits import LNbitsSettings


class SuperUserSettings(LNbitsSettings):
    lnbits_allowed_funding_sources: list[str] = Field(
        default=[
            "AlbyWallet",
            "BoltzWallet",
            "BlinkWallet",
            "BreezSdkWallet",
            "CoreLightningRestWallet",
            "CoreLightningWallet",
            "EclairWallet",
            "FakeWallet",
            "LNPayWallet",
            "LNbitsWallet",
            "LnTipsWallet",
            "LndRestWallet",
            "LndWallet",
            "OpenNodeWallet",
            "PhoenixdWallet",
            "VoidWallet",
            "ZBDWallet",
            "NWCWallet",
        ]
    )
