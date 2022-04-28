from sqlite3 import Row
from typing import Optional

from fastapi.param_functions import Query
from pydantic import BaseModel
from pydantic.main import BaseModel


class CreateCharge(BaseModel):
    onchainwallet: str = Query(None)
    lnbitswallet: str = Query(None)
    description: str = Query(...)
    webhook: str = Query(None)
    completelink: str = Query(None)
    completelinktext: str = Query(None)
    time: int = Query(..., ge=1)
    amount: int = Query(..., ge=1)


class createTip(BaseModel):
    id: str
    wallet: str
    sats: int
    tipjar: int
    name: str = "Anonymous"
    message: str = ""


class Tip(BaseModel):
    """A Tip represents a single donation"""

    id: str  # This ID always corresponds to a satspay charge ID
    wallet: str
    name: str  # Name of the donor
    message: str  # Donation message
    sats: int
    tipjar: int  # The ID of the corresponding tip jar

    @classmethod
    def from_row(cls, row: Row) -> "Tip":
        return cls(**dict(row))


class createTipJar(BaseModel):
    name: str
    wallet: str
    webhook: str = None
    onchain: str = None


class createTips(BaseModel):
    name: str
    sats: str
    tipjar: str
    message: str


class TipJar(BaseModel):
    """A TipJar represents a user's tip jar"""

    id: int
    name: str  # The name of the donatee
    wallet: str  # Lightning wallet
    onchain: Optional[str]  # Watchonly wallet
    webhook: Optional[str]  # URL to POST tips to

    @classmethod
    def from_row(cls, row: Row) -> "TipJar":
        return cls(**dict(row))
