import json
from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreatePaywall(BaseModel):
    url: str = Query(...)
    memo: str = Query(...)
    description: str = Query(None)
    amount: int = Query(..., ge=0)
    remembers: bool = Query(...)
    webhook: str = Query(None)


class CreatePaywallInvoice(BaseModel):
    amount: int = Query(..., ge=1)


class CheckPaywallInvoice(BaseModel):
    payment_hash: str = Query(...)


class Paywall(BaseModel):
    id: str
    wallet: str
    url: str
    memo: str
    description: Optional[str]
    amount: int
    time: int
    remembers: bool
    extras: Optional[dict]
    webhook: Optional[str]

    @classmethod
    def from_row(cls, row: Row) -> "Paywall":
        data = dict(row)
        data["remembers"] = bool(data["remembers"])
        data["extras"] = json.loads(data["extras"]) if data["extras"] else None
        return cls(**data)
