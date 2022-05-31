from sqlite3 import Row

from fastapi.param_functions import Query
from pydantic import BaseModel
from typing import Optional


class CreateUserData(BaseModel):
    user_name: str = Query(...)
    wallet_name: str = Query(...)
    admin_id: str = Query(...)
    discord_id: str = Query("")

class CreateUserWallet(BaseModel):
    user_id: str = Query(...)
    wallet_name: str = Query(...)
    admin_id: str = Query(...)


class Users(BaseModel):
    id: str
    name: str
    admin: str
    discord_id: str

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
