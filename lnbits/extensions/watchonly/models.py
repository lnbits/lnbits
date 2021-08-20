from sqlite3 import Row
from pydantic import BaseModel


class Wallets(BaseModel):
    id: str
    user: str
    masterpub: str
    title: str
    address_no: int
    balance: int

    @classmethod
    def from_row(cls, row: Row) -> "Wallets":
        return cls(**dict(row))


class Mempool(BaseModel):
    user: str
    endpoint: str

    @classmethod
    def from_row(cls, row: Row) -> "Mempool":
        return cls(**dict(row))


class Addresses(BaseModel):
    id: str
    address: str
    wallet: str
    amount: int

    @classmethod
    def from_row(cls, row: Row) -> "Addresses":
        return cls(**dict(row))
