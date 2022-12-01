from sqlite3 import Row
from typing import List, Union

from fastapi import Query
from pydantic import BaseModel


class Cashu(BaseModel):
    id: str = Query(None)
    name: str = Query(None)
    wallet: str = Query(None)
    tickershort: str = Query(None)
    fraction: bool = Query(None)
    maxsats: int = Query(0)
    coins: int = Query(0)
    keyset_id: str = Query(None)

    @classmethod
    def from_row(cls, row: Row):
        return cls(**dict(row))


class Pegs(BaseModel):
    id: str
    wallet: str
    inout: str
    amount: str

    @classmethod
    def from_row(cls, row: Row):
        return cls(**dict(row))


class PayLnurlWData(BaseModel):
    lnurl: str


class Promises(BaseModel):
    id: str
    amount: int
    B_b: str
    C_b: str
    cashu_id: str


class Proof(BaseModel):
    amount: int
    secret: str
    C: str
    reserved: bool = False  # whether this proof is reserved for sending
    send_id: str = ""  # unique ID of send attempt
    time_created: str = ""
    time_reserved: str = ""

    @classmethod
    def from_row(cls, row: Row):
        return cls(
            amount=row[0],
            C=row[1],
            secret=row[2],
            reserved=row[3] or False,
            send_id=row[4] or "",
            time_created=row[5] or "",
            time_reserved=row[6] or "",
        )

    @classmethod
    def from_dict(cls, d: dict):
        assert "secret" in d, "no secret in proof"
        assert "amount" in d, "no amount in proof"
        return cls(
            amount=d.get("amount"),
            C=d.get("C"),
            secret=d.get("secret"),
            reserved=d.get("reserved") or False,
            send_id=d.get("send_id") or "",
            time_created=d.get("time_created") or "",
            time_reserved=d.get("time_reserved") or "",
        )

    def to_dict(self):
        return dict(amount=self.amount, secret=self.secret, C=self.C)

    def __getitem__(self, key):
        return self.__getattribute__(key)

    def __setitem__(self, key, val):
        self.__setattr__(key, val)


class Proofs(BaseModel):
    """TODO: Use this model"""

    proofs: List[Proof]


class Invoice(BaseModel):
    amount: int
    pr: str
    hash: str
    issued: bool = False

    @classmethod
    def from_row(cls, row: Row):
        return cls(
            amount=int(row[0]),
            pr=str(row[1]),
            hash=str(row[2]),
            issued=bool(row[3]),
        )


class BlindedMessage(BaseModel):
    amount: int
    B_: str


class BlindedSignature(BaseModel):
    amount: int
    C_: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            amount=d["amount"],
            C_=d["C_"],
        )


class MintPayloads(BaseModel):
    blinded_messages: List[BlindedMessage] = []


class SplitPayload(BaseModel):
    proofs: List[Proof]
    amount: int
    output_data: MintPayloads


class CheckPayload(BaseModel):
    proofs: List[Proof]


class MeltPayload(BaseModel):
    proofs: List[Proof]
    amount: int
    invoice: str
