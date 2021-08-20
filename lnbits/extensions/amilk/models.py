from sqlite3 import Row
from pydantic import BaseModel
#from typing import NamedTuple


class AMilk(BaseModel):
    id: str
    wallet: str
    lnurl: str
    atime: int
    amount: int
