from sqlite3 import Row
from typing import NamedTuple, Optional


class Donation(NamedTuple):
    id: str
    name: str
    message: str
    cur_code: str
    sats: int
    amount: float
    service: int
    posted: bool

    @classmethod
    def from_row(cls, row: Row) -> "Donation":
        return cls(**dict(row))


class Service(NamedTuple):
    id: int
    state: str
    twitchuser: str
    client_id: str
    client_secret: str
    wallet: str
    onchain: str
    servicename: str
    authenticated: bool
    token: Optional[int]

    @classmethod
    def from_row(cls, row: Row) -> "Service":
        return cls(**dict(row))
