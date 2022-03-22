from sqlite3 import Row
from typing import List, Optional

from fastapi import Query
from pydantic import BaseModel, Field


class UpdateAdminSettings(BaseModel):
    # users
    admin_users: str = Query(None)
    allowed_users: str = Query(None)
    admin_ext: str = Query(None)
    disabled_ext: str = Query(None)
    funding_source: str = Query(None)
    # ops
    force_https: bool = Query(None)
    service_fee: float = Query(None, ge=0)
    hide_api: bool = Query(None)
    # Change theme
    site_title: str = Query("LNbits")
    site_tagline: str = Query("free and open-source lightning wallet")
    site_description: str = Query(None)
    default_wallet_name: str = Query("LNbits wallet")
    denomination: str = Query("sats")
    theme: str = Query(None)
    ad_space: str = Query(None)

class Admin(BaseModel):
    # users
    user: str
    admin_users: Optional[str]
    allowed_users: Optional[str]
    admin_ext: Optional[str]
    disabled_ext: Optional[str]
    funding_source: Optional[str]
    # ops
    data_folder: Optional[str]
    database_url: Optional[str]
    force_https: bool = Field(default=True)
    service_fee: float = Field(default=0)
    hide_api: bool = Field(default=False)
    # Change theme
    site_title: Optional[str]
    site_tagline: Optional[str]
    site_description: Optional[str]
    default_wallet_name: Optional[str]
    denomination: str = Field(default="sats")
    theme: Optional[str]
    ad_space: Optional[str]

    @classmethod
    def from_row(cls, row: Row) -> "Admin":
        data = dict(row)
        return cls(**data)

class Funding(BaseModel):
    id: str
    backend_wallet: str
    endpoint: str = Query(None)
    port: str = Query(None)
    read_key: str = Query(None)
    invoice_key: str = Query(None)
    admin_key: str = Query(None)
    cert: str = Query(None)
    balance: int = Query(None)
    selected: int

    @classmethod
    def from_row(cls, row: Row) -> "Funding":
        data = dict(row)
        return cls(**data)
