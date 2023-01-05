from sqlite3 import Row

from fastapi import Query
from pydantic import BaseModel


class Gerty(BaseModel):
    id: str = Query(None)
    name: str
    refresh_time: int = Query(None)
    utc_offset: int = Query(None)
    wallet: str = Query(None)
    type: str
    lnbits_wallets: str = Query(
        None
    )  # Wallets to keep an eye on, {"wallet-id": "wallet-read-key, etc"}
    mempool_endpoint: str = Query(None)  # Mempool endpoint to use
    exchange: str = Query(
        None
    )  # BTC <-> Fiat exchange rate to pull ie "USD", in 0.0001 and sats
    display_preferences: str = Query(None)
    urls: str = Query(None)

    @classmethod
    def from_row(cls, row: Row) -> "Gerty":
        return cls(**dict(row))


#########MEMPOOL MODELS###########


class MempoolEndpoint(BaseModel):
    fees_recommended: str = "/api/v1/fees/recommended"
    hashrate_1w: str = "/api/v1/mining/hashrate/1w"
    hashrate_1m: str = "/api/v1/mining/hashrate/1m"
    statistics: str = "/api/v1/lightning/statistics/latest"
    difficulty_adjustment: str = "/api/v1/difficulty-adjustment"
    tip_height: str = "/api/blocks/tip/height"
    mempool: str = "/api/mempool"


class Mempool(BaseModel):
    id: str = Query(None)
    mempool_endpoint: str = Query(None)
    endpoint: str = Query(None)
    data: str = Query(None)
    time: int = Query(None)
