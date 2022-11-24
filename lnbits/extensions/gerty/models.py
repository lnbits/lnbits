from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class Gerty(BaseModel):
    id: str = Query(None)
    name: str
    refresh_time: int = Query(None)
    utc_offset: int = Query(None)
    type: str
    lnbits_wallets: str = Query(
        None
    )  # Wallets to keep an eye on, {"wallet-id": "wallet-read-key, etc"}
    mempool_endpoint: str = Query(None)  # Mempool endpoint to use
    exchange: str = Query(
        None
    )  # BTC <-> Fiat exchange rate to pull ie "USD", in 0.0001 and sats
    display_preferences: str = Query(None)

    @classmethod
    def from_row(cls, row: Row) -> "Gerty":
        return cls(**dict(row))


#########MEMPOOL MODELS###########

class Fees_recommended(BaseModel):
    data: str = Query(None)
    time: int = Query(None)

class Hashrate_1w(BaseModel):
    data: str = Query(None)
    time: int = Query(None)

class Hashrate_1m(BaseModel):
    data: str = Query(None)
    time: int = Query(None)

class Statistics(BaseModel):
    data: str = Query(None)
    time: int = Query(None)

class Difficulty_adjustment(BaseModel):
    data: str = Query(None)
    time: int = Query(None)

class Tip_height(BaseModel):
    data: str = Query(None)
    time: int = Query(None)

class Mempool(BaseModel):
    data: str = Query(None)
    time: int = Query(None)