from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, validator


class CreateWallet(BaseModel):
    masterpub: str = Field(..., min_length=1, max_length=10000)
    title: str = Field(..., min_length=1, max_length=100)
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"
    meta: str = "{}"


class WalletAccount(BaseModel):
    id: str
    wallet_id: str
    masterpub: str
    fingerprint: str
    title: str
    address_no: int
    balance: int
    type: str | None = ""
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"
    meta: str = "{}"
    wallet_kind: str = "watch"
    backup_confirmed: bool = False


class Address(BaseModel):
    id: str
    address: str
    wallet: str
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


class Config(BaseModel):
    explorer_provider: Literal["auto", "lnbits", "mempool"] = "auto"
    mempool_endpoint: str = "https://mempool.space"
    receive_gap_limit: int = Field(default=20, ge=1, le=1000)
    change_gap_limit: int = Field(default=5, ge=1, le=1000)
    sats_denominated: bool = True
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"

    @validator("mempool_endpoint")
    @classmethod
    def valid_endpoint(cls, value):
        url = urlsplit(value)
        if (
            url.scheme not in ("https", "http")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Enter an HTTP(S) explorer URL without credentials or query"
            )
        return value.rstrip("/")


class ConfigResponse(Config):
    lnbits_explorer_network: str | None = None
    explorer_url: str


class ConfigDb(BaseModel):
    wallet_id: str
    json_data: Config
