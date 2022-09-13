from sqlite3 import Row
from typing import List, Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class CreateWallet(BaseModel):
    masterpub: str = Query("")
    title: str = Query("")
    network: str = "Mainnet"


class WalletAccount(BaseModel):
    id: str
    user: str
    masterpub: str
    fingerprint: str
    title: str
    address_no: int
    balance: int
    type: Optional[str] = ""
    network: str = "Mainnet"

    @classmethod
    def from_row(cls, row: Row) -> "WalletAccount":
        return cls(**dict(row))


class Address(BaseModel):
    id: str
    address: str
    wallet: str
    amount: int = 0
    branch_index: int = 0
    address_index: int
    note: str = None
    has_activity: bool = False

    @classmethod
    def from_row(cls, row: Row) -> "Address":
        return cls(**dict(row))


class TransactionInput(BaseModel):
    tx_id: str
    vout: int
    amount: int
    address: str
    branch_index: int
    address_index: int
    wallet: str
    tx_hex: str


class TransactionOutput(BaseModel):
    amount: int
    address: str
    branch_index: int = None
    address_index: int = None
    wallet: str = None


class MasterPublicKey(BaseModel):
    id: str
    public_key: str
    fingerprint: str


class CreatePsbt(BaseModel):
    masterpubs: List[MasterPublicKey]
    inputs: List[TransactionInput]
    outputs: List[TransactionOutput]
    fee_rate: int
    tx_size: int


class ExtractPsbt(BaseModel):
    psbtBase64 = ""  # // todo snake case
    inputs: List[TransactionInput]


class SignedTransaction(BaseModel):
    tx_hex: Optional[str]
    tx_json: Optional[str]


class BroadcastTransaction(BaseModel):
    tx_hex: str


class Config(BaseModel):
    mempool_endpoint = "https://mempool.space"
    receive_gap_limit = 20
    change_gap_limit = 5
    sats_denominated = True
    network = "Mainnet"
