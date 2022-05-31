import json

from sqlite3 import Row
from pydantic import BaseModel
from typing import Optional


class Paywall(BaseModel):
    id: str
    wallet: str
    url: str
    memo: str
    description: str
    amount: int
    time: int
    remembers: bool
    extras: Optional[dict]

    @classmethod
    def from_row(cls, row: Row) -> "Paywall":
        data = dict(row)
        data["remembers"] = bool(data["remembers"])
        data["extras"] = json.loads(data["extras"]) if data["extras"] else None
        return cls(**data)
