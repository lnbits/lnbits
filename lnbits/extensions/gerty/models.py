from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel



class Gerty(BaseModel):
    id: str = Query(None)
    name: str
    wallet: str
    lnbits_wallets: str = Query(None) # Wallets to keep an eye on, {"wallet-id": "wallet-read-key, etc"}
    mempool_endpoint: str = Query(None) # Mempool endpoint to use
    exchange: str = Query(None) # BTC <-> Fiat exchange rate to pull ie "USD", in 0.0001 and sats
    show_lnbits_wallets_balance: bool = Query(False)
    show_sats_quote: bool = Query(False)
    show_pieter_wuille_facts: bool = Query(False)
    show_exchange_market_rate: bool = Query(False)
    show_onchain_difficulty_epoch_progress: bool = Query(False)
    show_onchain_difficulty_retarget_date: bool = Query(False)
    show_onchain_difficulty_blocks_remaining: bool = Query(False)
    show_onchain_difficulty_epoch_time_remaining: bool = Query(False)
    show_onchain_mempool_recommended_fees: bool = Query(False)
    show_onchain_mempool_number_of_tx: bool = Query(False)
    show_mining_current_hash_rate: bool = Query(False)
    show_mining_current_difficulty: bool = Query(False)
    show_lightning_channel_count: bool = Query(False)
    show_lightning_node_count: bool = Query(False)
    show_lightning_tor_node_count: bool = Query(False)
    show_lightning_clearnet_nodes: bool = Query(False)
    show_lightning_unannounced_nodes: bool = Query(False)
    show_lightning_average_channel_capacity: bool = Query(False)


    @classmethod
    def from_row(cls, row: Row) -> "Gerty":
        return cls(**dict(row))