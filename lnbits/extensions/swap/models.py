import json
from typing import Dict, List, Optional

from fastapi.params import Query
from pydantic.main import BaseModel
from sqlalchemy.engine import base  # type: ignore

## SWAP OUT

class SwapOut(BaseModel):
    id: str
    wallet: str
    onchainwallet: Optional[str]
    onchainaddress: Optional[str]
    amount: int
    recurrent: bool
    fee: int
    time: int

class CreateSwapOut(BaseModel):
    wallet: str = Query(...)
    onchainwallet: str = Query(None)
    onchainaddress: str = Query("")
    amount: int = Query(..., ge=1) #I'd set a minimum amount to prevent dust 1000/5000 ??
    recurrent: bool = Query(False)
    fee: int = Query(..., ge=1)

## RECURRENT

class Recurrent(BaseModel):
    id: str
    wallet: str
    onchainwallet: Optional[str]
    onchainaddress: Optional[str]
    threshold: int
    fee: int
    time: int

class CreateRecurrent(BaseModel):
    wallet: str = Query(...)
    onchainwallet: str = Query(None)
    onchainaddress: str = Query("")
    threshold: int = Query(..., ge=1) #I'd set a minimum amount to prevent dust 1000/5000 ??
    fee: int = Query(..., ge=1)

## SWAP IN

class Txid(BaseModel):
    txid: str = Query(...)

class Offer(BaseModel):
    addr: str
    sat: int

class CreateReserve(BaseModel):
    addresses: List[Offer] = Query(...)
    fees: int

class SwapIn(BaseModel):
    id: str
    wallet: str
    session_id: str
    reserve_id: str
    txid: Optional[str]
    amount: Optional[int]
    done: bool
    time: int

class CreateSwapIn(BaseModel):
    wallet: str = Query(...)
    session_id: str = Query(...)
    reserve_id: str = Query(...)
    amount: int = Query(..., ge=1)
