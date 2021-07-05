from typing import NamedTuple
from sqlite3 import Row


class Users(NamedTuple):
    id: str
    name: str
    admin: str
    email: str
    password: str


class Wallets(NamedTuple):
    id: str
    admin: str
    name: str
    user: str
    adminkey: str
    inkey: str

    @classmethod
    def from_row(cls, row: Row) -> "Wallets":
        return cls(**dict(row))
