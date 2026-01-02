from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from lnbits.db import FilterModel


class CreateOffer(BaseModel):
    memo: str
    amount_msat: int | None = None
    extra: dict | None = {}
    expiry: datetime | None = None
    webhook: str | None = None


class Offer(BaseModel):
    offer_id: str
    wallet_id: str
    amount: int | None = None
    active: bool
    single_use: bool
    used: bool
    bolt12: str
    memo: str | None = None
    expiry: datetime | None = None
    webhook: str | None = None
    webhook_status: str | None = None
    tag: str | None = None
    extension: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        return self.active is True

    @property
    def is_inactive(self) -> bool:
        return self.active is False

    @property
    def is_single_use(self) -> bool:
        return self.single_use is True

    @property
    def is_multiple_use(self) -> bool:
        return self.single_use is False

    @property
    def is_used(self) -> bool:
        return self.used is True

    @property
    def is_unused(self) -> bool:
        return self.used is False

    @property
    def msat(self) -> int | None:
        return self.amount

    @property
    def sat(self) -> int | None:
        return int(self.amount / 1000) if self.amount else None

    @property
    def is_expired(self) -> bool:
        return self.expiry < datetime.now(timezone.utc) if self.expiry else False


class OfferFilters(FilterModel):
    __search_fields__ = [
        "memo",
        "amount",
        "offer_id",
        "wallet_id",
        "tag",
        "active",
        "single_use",
        "used",
    ]

    __sort_fields__ = ["created_at", "updated_at", "amount", "fee", "memo", "tag"]

    active: bool | None
    single_use: bool | None
    used: bool | None
    tag: str | None
    offer_id: str | None
    amount: int | None
    memo: str | None
    wallet_id: str | None


class DecodeOffer(BaseModel):
    data: str
    filter_fields: list[str] | None = []


class OffersStatusCount(BaseModel):
    active: int = 0
    single_use: int = 0
    used: int = 0
