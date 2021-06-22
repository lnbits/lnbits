from sqlite3 import Row
from typing import NamedTuple, Optional


class Donations(NamedTuple):
    id: str
    name: str
    cur_code: str
    sats: int
    amount: float
    service: int
    posted: bool

    @classmethod
    def from_row(cls, row: Row) -> "Donations":
        return cls(**dict(row))


class Services(NamedTuple):
    id: int
    twitchuser: str
    client_id: str
    client_secret: str
    wallet: str
    onchain: str
    servicename: str
    authenticated: bool
    token: Optional[int]

    @classmethod
    def from_row(cls, row: Row) -> "Services":
        return cls(**dict(row))
