from pydantic.main import BaseModel


class Token(BaseModel):
    deezy_token: str


class LnToBtcSwap(BaseModel):
    amount_sats: int
    on_chain_address: str
    on_chain_sats_per_vbyte: int
    bolt11_invoice: str
    fee_sats: int
    txid: str = ""
    tx_hex: str = ""
    created_at: str = ""


class UpdateLnToBtcSwap(BaseModel):
    txid: str
    tx_hex: str
    bolt11_invoice: str


class BtcToLnSwap(BaseModel):
    ln_address: str
    on_chain_address: str
    secret_access_key: str
    commitment: str
    signature: str
    created_at: str = ""
