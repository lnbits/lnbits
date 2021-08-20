from sqlite3 import Row
from pydantic import BaseModel
#from typing import NamedTuple


class TPoS(BaseModel):
    id: str
    wallet: str
    name: str
    currency: str

    @classmethod
    def from_row(cls, row: Row) -> "TPoS":
        return cls(**dict(row))
