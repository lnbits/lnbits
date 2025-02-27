from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from lnbits.db import FilterModel
from lnbits.settings import settings


class AuditEntry(BaseModel):
    component: str | None = None
    ip_address: str | None = None
    user_id: str | None = None
    path: str | None = None
    request_type: str | None = None
    request_method: str | None = None
    request_details: str | None = None
    response_code: str | None = None
    duration: float
    delete_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def __init__(self, **data):
        super().__init__(**data)
        retention_days = max(0, settings.lnbits_audit_retention_days) or 365
        self.delete_at = self.created_at + timedelta(days=retention_days)


class AuditFilters(FilterModel):
    __search_fields__ = [
        "ip_address",
        "user_id",
        "path",
        "request_method",
        "response_code",
        "component",
    ]
    __sort_fields__ = [
        "created_at",
        "duration",
    ]

    ip_address: str | None = None
    user_id: str | None = None
    path: str | None = None
    request_method: str | None = None
    response_code: str | None = None
    component: str | None = None


class AuditCountStat(BaseModel):
    field: str = ""
    total: float = 0


class AuditStats(BaseModel):
    request_method: list[AuditCountStat] = []
    response_code: list[AuditCountStat] = []
    component: list[AuditCountStat] = []
    long_duration: list[AuditCountStat] = []
