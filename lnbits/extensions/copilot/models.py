from sqlite3 import Row
from typing import NamedTuple
import time


class Copilots(NamedTuple):
    id: str
    user: str
    title: str
    animation1: str
    animation2: str
    animation3: str
    animation1threshold: int
    animation2threshold: int
    animation3threshold: int
    animation1webhook: str
    animation2webhook: str
    animation3webhook: str
    show_message: bool
    amount: int
    lnurl_title: str
    show_message: int
    show_ack: int
    amount_made: int

    @classmethod
    def from_row(cls, row: Row) -> "Copilots":
        return cls(**dict(row))
