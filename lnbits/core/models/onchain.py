"""Models for onchain addresses and transactions."""

from typing import Literal

from pydantic import BaseModel, Field


class Address(BaseModel):
    id: str
    address: str
    walet_id: str
    amount: int = 0
    branch_index: int = 0
    address_index: int
    note: str | None = None
    has_activity: bool = False


class TransactionInput(BaseModel):
    tx_id: str
    vout: int
    amount: int
    address: str
    branch_index: int
    address_index: int
    wallet: str
    tx_hex: str = Field(..., min_length=1, max_length=8000000)


class TransactionOutput(BaseModel):
    amount: int
    address: str
    branch_index: int | None = None
    address_index: int | None = None
    wallet: str | None = None


class MasterPublicKey(BaseModel):
    id: str
    public_key: str
    fingerprint: str


class CreatePsbt(BaseModel):
    masterpubs: list[MasterPublicKey]
    inputs: list[TransactionInput] = Field(..., min_items=1, max_items=200)
    outputs: list[TransactionOutput] = Field(..., min_items=1, max_items=100)
    fee_rate: int
    tx_size: int


class SerializedTransaction(BaseModel):
    tx_hex: str = Field(..., min_length=1, max_length=8000000)
    network: Literal["Mainnet", "Testnet", "Testnet4"] | None = None


class ExtractPsbt(BaseModel):
    psbt_base64: str = Field(..., alias="psbtBase64", min_length=1)
    expected_psbt_base64: str | None = Field(
        None, alias="expectedPsbtBase64", min_length=1
    )
    inputs: list[SerializedTransaction]
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"

    class Config:
        allow_population_by_field_name = True


class ExtractTx(BaseModel):
    tx_hex: str = Field(..., min_length=1, max_length=8000000)
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"


class SignedTransaction(BaseModel):
    tx_hex: str | None
    tx_json: str | None
