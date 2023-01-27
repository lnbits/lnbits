from sqlite3 import Row
from typing import Optional

from fastapi.param_functions import Query
from pydantic import BaseModel, Field


class CreateUserData(BaseModel):
    user_name: str = Query(..., description="Name of the user")
    wallet_name: str = Query(..., description="Name of the user")
    admin_id: str = Query(..., description="Id of the user which will administer this new user")
    email: str = Query("")
    password: str = Query("")


class CreateUserWallet(BaseModel):
    user_id: str = Query(..., description="Target user for this new wallet")
    wallet_name: str = Query(..., description="Name of the new wallet to create")
    admin_id: str = Query(..., description="Id of the user which will administer this new wallet")


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
