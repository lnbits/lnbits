from typing import NamedTuple
from sqlite3 import Row

class Admin(NamedTuple):
    user: str
    site_title: str
    tagline: str
    allowed_users: str
    default_wallet_name: str
    data_folder: str
    disabled_ext: str
    force_https: str
    service_fee: str
    funding_source: str

    @classmethod
    def from_row(cls, row: Row) -> "Admin":
        data = dict(row)
        return cls(**data)

class Funding(NamedTuple):
    id: str
    backend_wallet: str
    endpoint: str
    port: str
    read_key: str
    invoice_key: str
    admin_key: str
    cert: str
    balance: int
    selected: int

    @classmethod
    def from_row(cls, row: Row) -> "Funding":
        data = dict(row)
        return cls(**data)
