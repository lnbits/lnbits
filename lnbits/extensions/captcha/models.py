import json

from sqlite3 import Row
from typing import NamedTuple, Optional


class Captcha(NamedTuple):
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
    def from_row(cls, row: Row) -> "Captcha":
        data = dict(row)
        data["remembers"] = bool(data["remembers"])
        data["extras"] = json.loads(data["extras"]) if data["extras"] else None
        return cls(**data)
