from sqlite3 import Row
from fastapi.param_functions import Query
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
