# from sqlite3 import Row
from typing import NamedTuple

class Conference(NamedTuple):
    id: str
    admin: str

class Participant(NamedTuple):
    id: str
    conference: str
    user: str
    wallet: str


