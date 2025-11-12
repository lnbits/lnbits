from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from lnbits.db import FilterModel


class AssetInfo(BaseModel):
    id: str
    mime_type: str
    name: str
    is_public: bool = False
    size_bytes: int
    thumbnail_base64: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Asset(AssetInfo):
    user_id: str
    data: bytes


class AssetUpdate(BaseModel):
    name: str | None = None
    is_public: bool | None = None


class AssetFilters(FilterModel):
    __search_fields__ = ["name"]
    __sort_fields__ = [
        "created_at",
        "name",
    ]

    name: str | None = None
