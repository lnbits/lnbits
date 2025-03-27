from __future__ import annotations

from typing import Callable

from pydantic import BaseModel


def _do_nothing(*_):
    pass


class CoreAppExtra:
    register_new_ext_routes: Callable = _do_nothing
    register_new_ratelimiter: Callable


class ConversionData(BaseModel):
    from_: str = "sat"
    amount: float
    to: str = "usd"


class Callback(BaseModel):
    callback: str


class BalanceDelta(BaseModel):
    lnbits_balance_sats: int
    node_balance_sats: int

    @property
    def delta_sats(self) -> int:
        return int(self.lnbits_balance_sats - self.node_balance_sats)


class SimpleStatus(BaseModel):
    success: bool
    message: str


class SimpleItem(BaseModel):
    id: str
    name: str


class DbVersion(BaseModel):
    db: str
    version: int


class Image(BaseModel):
    filename: str
    directory: str = "library"
