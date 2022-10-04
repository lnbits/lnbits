from sqlite3 import Row
from typing import List, Optional

from fastapi import Query
from pydantic import BaseModel, Field

class UpdateSettings(BaseModel):
    lnbits_admin_users: str = Query(None)
    lnbits_allowed_users: str = Query(None)
    lnbits_admin_ext: str = Query(None)
    lnbits_disabled_ext: str = Query(None)
    lnbits_funding_source: str = Query(None)
    lnbits_force_https: bool = Query(None)
    lnbits_reserve_fee_min: int = Query(None, ge=0)
    lnbits_reserve_fee_percent: float = Query(None, ge=0)
    lnbits_service_fee: float = Query(None, ge=0)
    lnbits_hide_api: bool = Query(None)
    lnbits_site_title: str = Query("LNbits")
    lnbits_site_tagline: str = Query("free and open-source lightning wallet")
    lnbits_site_description: str = Query(None)
    lnbits_default_wallet_name: str = Query("LNbits wallet")
    lnbits_denomination: str = Query("sats")
    lnbits_theme: str = Query(None)
    lnbits_custom_logo: str = Query(None)
    lnbits_ad_space: str = Query(None)
