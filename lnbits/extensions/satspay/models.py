from sqlite3 import Row
from typing import NamedTuple


class Charges(NamedTuple):
    id: str
    user: str
    description: str
    onchainwallet: str
    onchainaddress: str
    lnbitswallet: str
    payment_request: str
    payment_hash: str
    webhook: str
    time: str
    amount: int
    balance: int
    paid: bool
    timestamp: int

    @classmethod
    def from_row(cls, row: Row) -> "Charges":
        return cls(**dict(row))
