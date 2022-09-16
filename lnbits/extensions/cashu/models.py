from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class Cashu(BaseModel):
    id: str = Query(None)
    name: str = Query(None)
    wallet: str = Query(None)
    tickershort: str
    fraction: bool = Query(None)
    maxsats: int = Query(0)
    coins: int = Query(0)
    

    @classmethod
    def from_row(cls, row: Row) -> "TPoS":
        return cls(**dict(row))

class Pegs(BaseModel):
    id: str
    wallet: str
    inout: str
    amount: str


    @classmethod
    def from_row(cls, row: Row) -> "TPoS":
        return cls(**dict(row))

class PayLnurlWData(BaseModel):
    lnurl: str