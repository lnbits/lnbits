from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field

from lnbits.settings import settings


class AuditEntry(BaseModel):
    id: Optional[int] = None
    ip_address: Optional[str] = None
    user_id: Optional[str] = None
    path: Optional[str] = None
    route_path: Optional[str] = None
    request_type: Optional[str] = None
    request_method: Optional[str] = None
    query_string: Optional[str] = None
    response_code: Optional[str] = None
    duration: float
    delete_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def __init__(self, **data):
        super.__init__(**data)
        if settings.lnbits_audit_retention_days > 0:
            self.delete_at = self.created_at + timedelta(
                days=settings.lnbits_audit_retention_days
            )
