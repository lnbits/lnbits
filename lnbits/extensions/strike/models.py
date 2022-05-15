import time
from sqlite3 import Row
from typing import Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class CreateConfiguration(BaseModel):
    lnbits_wallet: str = Query(None)
    handle: str = Query(None)
    description: str = Query(None)


class StrikeConfiguration(BaseModel):
    id: str
    lnbits_wallet: str
    handle: str
    description: Optional[str]
    currency: Optional[str]
    timestamp: int

    @classmethod
    def from_row(cls, row: Row) -> "Configurations":
        return cls(**dict(row))

class StrikeForward(BaseModel):
    id: str
    lnbits_wallet: str
    handle: str
    message: Optional[str]
    sats_original: int
    sats_forwarded: Optional[int]
    msats_fee: Optional[int]
    amount: Optional[float]
    currency: Optional[str]
    spread: Optional[float]
    status: Optional[str]
    status_info: Optional[str]
    timestamp: int

    @classmethod
    def from_row(cls, row: Row) -> "Forwards":
        return cls(**dict(row))