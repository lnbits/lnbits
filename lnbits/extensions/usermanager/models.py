import json
from typing import NamedTuple, Dict
from sqlite3 import Row


class Users(NamedTuple):
    id: str
    name: str
    admin: str
    email: str
    password: str
    metadata: Dict
    custom_id: str

    @classmethod
    def from_row(cls, row: Row) -> "Users":
        return cls(
            id=row["id"],
            name=row["name"],
            admin=row["admin"],
            email=row["email"],
            password=row["password"],
            metadata=json.loads(row["metadata"] or "{}"),
            custom_id=row["custom_id"] or "",
        )


class Wallets(NamedTuple):
    id: str
    admin: str
    name: str
    user: str
    adminkey: str
    inkey: str

    @classmethod
    def from_row(cls, row: Row) -> "Wallets":
        return cls(**dict(row))
