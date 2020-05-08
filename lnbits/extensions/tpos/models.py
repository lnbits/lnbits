from sqlite3 import Row
from typing import NamedTuple


class TPoS(NamedTuple):
    id: str
    wallet: str
    name: str
    currency: str

    @classmethod
    def from_row(cls, row: Row) -> "TPoS":
        return cls(**dict(row))
