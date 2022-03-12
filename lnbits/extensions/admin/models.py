from sqlite3 import Row
from typing import List, Optional

from fastapi import Query
from pydantic import BaseModel


class UpdateAdminSettings(BaseModel):
    site_title: Optional[str]
    site_tagline: Optional[str]
    site_description: Optional[str]
    allowed_users: Optional[str]
    admin_users: Optional[str]
    default_wallet_name: Optional[str]
    data_folder: Optional[str]
    disabled_ext: Optional[str]
    force_https: Optional[bool]
    service_fee: Optional[float]
    funding_source: Optional[str]

class Admin(BaseModel):
    user: str
    site_title: Optional[str]
    site_tagline: Optional[str]
    site_description: Optional[str]
    allowed_users: Optional[str]
    admin_users: str
    default_wallet_name: str
    data_folder: str
    disabled_ext: str
    force_https: Optional[bool] = Query(True)
    service_fee: float
    funding_source: str

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
