from sqlite3 import Row
from typing import NamedTuple

class Charges(NamedTuple):
    id: str
    user: str
    wallet: str
    title: str
    address: str
    time_to_pay: str
    amount: int
    balance: int
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Payments":
        return cls(**dict(row))