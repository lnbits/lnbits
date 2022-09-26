from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel



class Gerty(BaseModel):
    id: str = Query(None)
    name: str
    wallet: str
    lnbits_wallets: str = Query(None) # Wallets to keep an eye on, {"wallet-id": "wallet-read-key, etc"}
    sats_quote: bool = Query(False) # Fetch Satoshi quotes
    exchange: str = Query(None) # BTC <-> Fiat exchange rate to pull ie "USD", in 0.0001 and sats
    onchain_sats: bool = Query(False) # Onchain stats
    ln_stats: bool = Query(False) # ln Sats

    @classmethod
    def from_row(cls, row: Row) -> "Gerty":
        return cls(**dict(row))