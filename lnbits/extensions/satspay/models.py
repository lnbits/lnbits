import json
from datetime import datetime, timedelta
from sqlite3 import Row
from typing import Optional

from fastapi.param_functions import Query
from pydantic import BaseModel

DEFAULT_MEMPOOL_CONFIG = (
    '{"mempool_endpoint": "https://mempool.space", "network": "Mainnet"}'
)


class CreateCharge(BaseModel):
    onchainwallet: str = Query(None)
    lnbitswallet: str = Query(None)
    description: str = Query(...)
    webhook: str = Query(None)
    completelink: str = Query(None)
    completelinktext: str = Query(None)
    custom_css: Optional[str]
    time: int = Query(..., ge=1)
    amount: int = Query(..., ge=1)
    extra: str = DEFAULT_MEMPOOL_CONFIG


class ChargeConfig(BaseModel):
    mempool_endpoint: Optional[str]
    network: Optional[str]
    webhook_success: Optional[bool] = False
    webhook_message: Optional[str]


class Charges(BaseModel):
    id: str
    description: Optional[str]
    onchainwallet: Optional[str]
    onchainaddress: Optional[str]
    lnbitswallet: Optional[str]
    payment_request: Optional[str]
    payment_hash: Optional[str]
    webhook: Optional[str]
    completelink: Optional[str]
    completelinktext: Optional[str] = "Back to Merchant"
    custom_css: Optional[str]
    extra: str = DEFAULT_MEMPOOL_CONFIG
    time: int
    amount: int
    balance: int
    timestamp: int

    @classmethod
    def from_row(cls, row: Row) -> "Charges":
        return cls(**dict(row))

    @property
    def time_left(self):
        now = datetime.utcnow().timestamp()
        start = datetime.fromtimestamp(self.timestamp)
        expiration = (start + timedelta(minutes=self.time)).timestamp()
        return (expiration - now) / 60

    @property
    def time_elapsed(self):
        return self.time_left < 0

    @property
    def paid(self):
        if self.balance >= self.amount:
            return True
        else:
            return False

    @property
    def config(self) -> ChargeConfig:
        charge_config = json.loads(self.extra)
        return ChargeConfig(**charge_config)

    def must_call_webhook(self):
        return self.webhook and self.paid and self.config.webhook_success == False


class SatsPayThemes(BaseModel):
    css_id: str = Query(None)
    title: str = Query(None)
    custom_css: str = Query(None)
    user: Optional[str]

    @classmethod
    def from_row(cls, row: Row) -> "SatsPayThemes":
        return cls(**dict(row))
