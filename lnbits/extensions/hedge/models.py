from sqlite3 import Row
from typing import Optional

from fastapi.param_functions import Query
from pydantic.main import BaseModel


class CreateCharge(BaseModel):
    onchainwallet: str = Query(None)
    lnbitswallet: str = Query(None)
    description: str = Query(...)
    hedgeuri: str = Query(None)
    completelink: str = Query(None)
    completelinktext: str = Query(None)
    time: int = Query(..., ge=1)
    amount: int = Query(..., ge=1)


class createHedgedWallet(BaseModel):
    ticker: str
    wallet: str
    hedgeuri: str = None
    onchain: str = None


class HedgedWallet(BaseModel):
    """A HedgedWallet represents a user's tip jar"""

    id: int
    ticker: str  # The ticker of the donatee
    wallet: str  # Lightning wallet
    onchain: Optional[str]  # Watchonly wallet
    hedgeuri: Optional[str]  # URL to POST tips to

    @classmethod
    def from_row(cls, row: Row) -> "HedgedWallet":
        return cls(**dict(row))
