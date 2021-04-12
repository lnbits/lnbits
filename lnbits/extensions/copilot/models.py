from sqlite3 import Row
from typing import NamedTuple
import time


class Copilots(NamedTuple):
    id: str
    user: str
    title: str
    animation: str
    show_message: bool
    amount: int
    lnurl_title: str

    @classmethod
    def from_row(cls, row: Row) -> "Charges":
        return cls(**dict(row))

    @property
    def paid(self):
        if self.balance >= self.amount:
            return True
        else:
            return False
