from sqlite3 import Row

from pydantic import BaseModel


class CreateTposData(BaseModel):
    name: str
    currency: str


class TPoS(BaseModel):
    id: str
    wallet: str
    name: str
    currency: str

    @classmethod
    def from_row(cls, row: Row) -> "TPoS":
        return cls(**dict(row))
