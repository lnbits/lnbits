from enum import Enum
from sqlite3 import Row
from typing import List, Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class RotateAddressData(BaseModel):
    pubkey: str


class CreateAddressData(BaseModel):
    domain_id: str
    local_part: str
    pubkey: str
    active: bool = False


class CreateDomainData(BaseModel):
    wallet: str
    currency: str
    amount: float = Query(..., ge=0.01)
    domain: str


class Domain(BaseModel):
    id: str
    wallet: str
    currency: str
    amount: int
    domain: str
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Domain":
        return cls(**dict(row))


class Address(BaseModel):
    id: str
    domain_id: str
    local_part: str
    pubkey: str
    active: bool
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Address":
        return cls(**dict(row))
