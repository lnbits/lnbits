from sqlite3 import Row
from typing import List, Union

from pydantic import BaseModel


class CashuError(BaseModel):
    code = "000"
    error = "CashuError"


class P2SHScript(BaseModel):
    script: str
    signature: str
    address: Union[str, None] = None

    @classmethod
    def from_row(cls, row: Row):
        return cls(
            address=row[0],
            script=row[1],
            signature=row[2],
            used=row[3],
        )


class Proof(BaseModel):
    amount: int
    secret: str = ""
    C: str
    script: Union[P2SHScript, None] = None
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
        assert "amount" in d, "no amount in proof"
        return cls(
            amount=d.get("amount"),
            C=d.get("C"),
            secret=d.get("secret") or "",
            reserved=d.get("reserved") or False,
            send_id=d.get("send_id") or "",
            time_created=d.get("time_created") or "",
            time_reserved=d.get("time_reserved") or "",
        )

    def to_dict(self):
        return dict(amount=self.amount, secret=self.secret, C=self.C)

    def to_dict_no_secret(self):
        return dict(amount=self.amount, C=self.C)

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


class MintRequest(BaseModel):
    blinded_messages: List[BlindedMessage] = []


class GetMintResponse(BaseModel):
    pr: str
    hash: str


class GetMeltResponse(BaseModel):
    paid: Union[bool, None]
    preimage: Union[str, None]


class SplitRequest(BaseModel):
    proofs: List[Proof]
    amount: int
    output_data: Union[
        MintRequest, None
    ] = None  # backwards compatibility with clients < v0.2.2
    outputs: Union[MintRequest, None] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.backwards_compatibility_v021()

    def backwards_compatibility_v021(self):
        # before v0.2.2: output_data, after: outputs
        if self.output_data:
            self.outputs = self.output_data
            self.output_data = None


class PostSplitResponse(BaseModel):
    fst: List[BlindedSignature]
    snd: List[BlindedSignature]


class CheckRequest(BaseModel):
    proofs: List[Proof]


class CheckFeesRequest(BaseModel):
    pr: str


class CheckFeesResponse(BaseModel):
    fee: Union[int, None]


class MeltRequest(BaseModel):
    proofs: List[Proof]
    amount: int = None  # deprecated
    invoice: str
