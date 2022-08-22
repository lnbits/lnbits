import json
from typing import Dict, List, Optional

from fastapi.params import Query
from pydantic.main import BaseModel
from sqlalchemy.engine import base  # type: ignore


class SubmarineSwap(BaseModel):
    id: str
    wallet: str
    amount: int
    payment_hash: str
    time: int
    status: str
    refund_privkey: str
    refund_address: str
    boltz_id: str
    expected_amount: int
    timeout_block_height: int
    address: str
    bip21: str
    redeem_script: str


class CreateSubmarineSwap(BaseModel):
    wallet: str = Query(...)  # type: ignore
    refund_address: str = Query(...)  # type: ignore
    amount: int = Query(...)  # type: ignore


class ReverseSubmarineSwap(BaseModel):
    id: str
    wallet: str
    amount: int
    onchain_address: str
    instant_settlement: bool
    time: int
    status: str
    boltz_id: str
    preimage: str
    claim_privkey: str
    lockup_address: str
    invoice: str
    onchain_amount: int
    timeout_block_height: int
    redeem_script: str


class CreateReverseSubmarineSwap(BaseModel):
    wallet: str = Query(...)  # type: ignore
    amount: int = Query(...)  # type: ignore
    instant_settlement: bool = Query(...)  # type: ignore
    # validate on-address, bcrt1 for regtest addresses
    onchain_address: str = Query(
        ..., regex="^(bcrt1|bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$"
    )  # type: ignore


class SwapStatus(BaseModel):
    swap_id: str
    wallet: str
    status: str = ""
    message: str = ""
    boltz: str = ""
    mempool: str = ""
    address: str = ""
    block_height: int = 0
    timeout_block_height: str = ""
    lockup: Optional[dict] = {}
    has_lockup: bool = False
    hit_timeout: bool = False
    confirmed: bool = True
    exists: bool = True
    reverse: bool = False
