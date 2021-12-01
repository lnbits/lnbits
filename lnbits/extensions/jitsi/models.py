# from sqlite3 import Row
from typing import NamedTuple

class Conference(NamedTuple):
    name: str
    admin: str  # This should be a foreign key into the LNBits.Users table.

class Participant(NamedTuple):
    id: str
    conference: str
    user: str
    wallet: str

class Message(NamedTuple):
    id:     str
    message:str
    stamp:  str      # FIXME(nochiel) Use a unix timestamp.

class Payment(NamedTuple):
    payer:  str
    payee:  str
    amount: int
    memo:   str
