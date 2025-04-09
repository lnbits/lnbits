from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from fastapi import Query
from pydantic import BaseModel, Field, validator

from lnbits.db import FilterModel
from lnbits.utils.exchange_rates import allowed_currencies
from lnbits.wallets import get_funding_source
from lnbits.wallets.base import (
    OfferStatus,
)


class OfferState(int, Enum):
    TRUE = 1
    FALSE = 0

    def __int__(self) -> int:
        return self.value


class CreateOffer(BaseModel):
    wallet_id: str
    bolt12: str
    amount_msat: int | None = None
    memo: str
    extra: dict | None = {}
    expiry: datetime | None = None
    webhook: str | None = None


class Offer(BaseModel):
    offer_id: str
    wallet_id: str
    amount: int | None = None
    active: int
    single_use: int
    bolt12: str
    memo: str | None = None
    expiry: datetime | None = None
    webhook: str | None = None
    webhook_status: str | None = None
    tag: str | None = None
    extension: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extra: dict = {}

    @property
    def is_active(self) -> bool:
        return not self.active == OfferState.FALSE.value

    @property
    def is_inactive(self) -> bool:
        return self.active == OfferState.FALSE.value

    @property
    def is_single_use(self) -> bool:
        return not self.single_use == OfferState.FALSE.value

    @property
    def is_multiple_use(self) -> bool:
        return self.single_use == OfferState.FALSE.value

    @property
    def msat(self) -> int:
        return self.amount

    @property
    def sat(self) -> int:
        return self.amount // 1000

    @property
    def is_expired(self) -> bool:
        return self.expiry < datetime.now(timezone.utc) if self.expiry else False

    async def check_status(self) -> OfferStatus:
        funding_source = get_funding_source()
        status = await funding_source.get_offer_status(self.offer_id)
        return status


class OfferFilters(FilterModel):
    __search_fields__ = ["memo", "amount", "wallet_id", "tag", "active", "single_use"]

    __sort_fields__ = ["created_at", "amount", "fee", "memo", "tag"]

    active: int | None
    single_use: int | None
    tag: str | None
    offer_id: str | None
    amount: int
    memo: str | None
    wallet_id: str | None


class OffersStatusCount(BaseModel):
    active: int = 0
    single_use: int = 0
