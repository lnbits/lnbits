from typing import NamedTuple

class Users(NamedTuple):
    id: str
    name: str
    admin: str
    email: str
    password: str

class Wallets(NamedTuple):
    id: str
    admin: str
    name: str
    user: str
    adminkey: str
    inkey: str


