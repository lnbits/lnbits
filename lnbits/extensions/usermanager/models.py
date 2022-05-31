from sqlite3 import Row
from pydantic import BaseModel


class Users(BaseModel):
    id: str
    name: str
    admin: str
    email: str
    password: str


class Wallets(BaseModel):
    id: str
    admin: str
    name: str
    user: str
    adminkey: str
    inkey: str

    @classmethod
    def from_row(cls, row: Row) -> "Wallets":
        return cls(**dict(row))
