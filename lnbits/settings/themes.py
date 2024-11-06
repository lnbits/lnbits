from __future__ import annotations

from typing import Optional

from pydantic import Field

from .lnbits import LNbitsSettings


class ThemesSettings(LNbitsSettings):
    lnbits_site_title: str = Field(default="LNbits")
    lnbits_site_tagline: str = Field(default="free and open-source lightning wallet")
    lnbits_site_description: Optional[str] = Field(
        default="The world's most powerful suite of bitcoin tools."
    )
    lnbits_show_home_page_elements: bool = Field(default=True)
    lnbits_default_wallet_name: str = Field(default="LNbits wallet")
    lnbits_custom_badge: Optional[str] = Field(default=None)
    lnbits_custom_badge_color: str = Field(default="warning")
    lnbits_theme_options: list[str] = Field(
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
    lnbits_custom_logo: Optional[str] = Field(default=None)
    lnbits_ad_space_title: str = Field(default="Supported by")
    lnbits_ad_space: str = Field(
        default="https://shop.lnbits.com/;/static/images/bitcoin-shop-banner.png;/static/images/bitcoin-shop-banner.png,https://affil.trezor.io/aff_c?offer_id=169&aff_id=33845;/static/images/bitcoin-hardware-wallet.png;/static/images/bitcoin-hardware-wallet.png,https://opensats.org/;/static/images/open-sats.png;/static/images/open-sats.png"
    )  # sneaky sneaky
    lnbits_ad_space_enabled: bool = Field(default=False)
    lnbits_allowed_currencies: list[str] = Field(default=[])
    lnbits_default_accounting_currency: Optional[str] = Field(default=None)
    lnbits_qr_logo: str = Field(default="/static/images/logos/lnbits.png")
