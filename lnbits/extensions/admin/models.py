from fastapi import Query
from pydantic import BaseModel


class UpdateSettings(BaseModel):
    lnbits_backend_wallet_class: str = Query(None)
    lnbits_admin_users: str = Query(None) #this should be List[str] ??
    lnbits_allowed_users: str = Query(None) #this should be List[str] ??
    lnbits_admin_ext: str = Query(None) #this should be List[str] ??
    lnbits_disabled_ext: str = Query(None) #this should be List[str] ??
    lnbits_funding_source: str = Query(None)
    lnbits_force_https: bool = Query(None)
    lnbits_reserve_fee_min: int = Query(None, ge=0)
    lnbits_reserve_fee_percent: float = Query(None, ge=0)
    lnbits_service_fee: float = Query(None, ge=0)
    lnbits_hide_api: bool = Query(None)
    lnbits_site_title: str = Query(None)
    lnbits_site_tagline: str = Query(None)
    lnbits_site_description: str = Query(None)
    lnbits_default_wallet_name: str = Query(None)
    lnbits_denomination: str = Query(None)
    lnbits_theme: str = Query(None)
    lnbits_custom_logo: str = Query(None)
    lnbits_ad_space: str = Query(None) #this should be List[str] ??
