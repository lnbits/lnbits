import json
from typing import Optional

from fastapi.params import Query
from pydantic.main import BaseModel  # type: ignore


class SwapOut(BaseModel):
    id: str
    wallet: str
    onchainwallet: Optional[str]
    onchainaddress: Optional[str]
    amount: int
    recurrent: bool
    fee: int
    time: int

class Recurrent(BaseModel):
    id: str
    wallet: str
    onchainwallet: Optional[str]
    onchainaddress: Optional[str]
    threshold: int
    fee: int
    time: int

class CreateSwapOut(BaseModel):
    wallet: str = Query(...)
    onchainwallet: str = Query(None)
    onchainaddress: str = Query("")
    amount: int = Query(..., ge=1) #I'd set a minimum amount to prevent dust 1000/5000 ??
    recurrent: bool = Query(False)
    fee: int = Query(..., ge=1)

class CreateRecurrent(BaseModel):
    wallet: str = Query(...)
    onchainwallet: str = Query(None)
    onchainaddress: str = Query("")
    threshold: int = Query(..., ge=1) #I'd set a minimum amount to prevent dust 1000/5000 ??
    fee: int = Query(..., ge=1)
