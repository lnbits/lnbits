from typing import NamedTuple
from pydantic import BaseModel

class Conference(BaseModel):
    name: str
    admin: str  # This should be a foreign key into the LNBits.Users table.

class Participant(BaseModel):
    id: str
    conference: str
    user: str
    wallet: str

class Message(BaseModel):
    id:     str
    message:str
    stamp:  str      # FIXME(nochiel) Use a unix timestamp.

class Payment(BaseModel):
    payer:  str
    payee:  str
    amount: int
    memo:   str
