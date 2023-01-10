from sqlite3 import Row
from typing import Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class CreateUserData(BaseModel):
    user_name: str = Query(...)
    wallet_name: str = Query(...)
    admin_id: str = Query(...)
    email: str = Query("")
    password: str = Query("")


class CreateUserWallet(BaseModel):
    user_id: str = Query(...)
    wallet_name: str = Query(...)
    admin_id: str = Query(...)


class User(BaseModel):
    id: str
    name: str
    admin: str
    email: Optional[str] = None
    password: Optional[str] = None


class Wallet(BaseModel):
    id: str
    admin: str
    name: str
    user: str
    adminkey: str
    inkey: str

    @classmethod
    def from_row(cls, row: Row) -> "Wallet":
        return cls(**dict(row))
