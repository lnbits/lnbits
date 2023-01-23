from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreatePeggingData(BaseModel):
    name: str
    percent: str
    currency: str = Query(None)
    base_url: str
    api_key: str
    api_secret: str
    api_passphrase: str


class Pegging(BaseModel):
    id: str
    name: str
    wallet: str
    percent: str
    currency: str = Query(None)
    base_url: str
    api_key: str
    api_secret: str
    api_passphrase: str

    @classmethod
    def from_row(cls, row: Row) -> "Pegging":
        return cls(**dict(row))
