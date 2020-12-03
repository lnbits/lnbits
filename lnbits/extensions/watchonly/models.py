from sqlite3 import Row
from typing import NamedTuple

class Wallets(NamedTuple):
    id: str
    user: str
    masterpub: str
    title: str
    address_no: int
    amount: int
    
    @classmethod
    def from_row(cls, row: Row) -> "Wallets":
        return cls(**dict(row))

class Payments(NamedTuple):
    id: str
    user: str
    wallet: str
    title: str
    address: str
    time_to_pay: str
    amount: int
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Payments":
        return cls(**dict(row))

class Addresses(NamedTuple):
    address: str
    wallet: str
    amount: int

    @classmethod
    def from_row(cls, row: Row) -> "Addresses":
        return cls(**dict(row))

class Mempool(NamedTuple):
    user: str
    endpoint: str
    
    @classmethod
    def from_row(cls, row: Row) -> "Mempool":
        return cls(**dict(row))