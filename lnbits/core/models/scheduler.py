import json
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, validator

from lnbits.db import FilterModel
from lnbits.utils.cron import normalize_cron


class SchedulePolicy(BaseModel):
    handler: str = Field(..., regex=r"^[A-Za-z0-9_-]{1,128}$")
    cron_expression: str = Field(..., min_length=1, max_length=256)
    timezone: str = Field(default="UTC", max_length=128)

    class Config:
        extra = "forbid"

    @validator("cron_expression")
    def validate_cron(cls, expression: str) -> str:
        return normalize_cron(expression)

    @validator("timezone")
    def validate_timezone(cls, zone: str) -> str:
        try:
            ZoneInfo(zone)
        except (KeyError, ValueError) as exc:
            raise ValueError("Unknown IANA timezone.") from exc
        return zone


def parse_schedule_policies(policies: list[Any] | None) -> dict[str, SchedulePolicy]:
    if not policies:
        raise ValueError("Scheduling permission requires per-handler cron policies.")
    parsed: dict[str, SchedulePolicy] = {}
    for policy in policies:
        if not isinstance(policy, dict):
            raise ValueError("Schedule policy must be an object.")
        schedule = SchedulePolicy.parse_obj(policy)
        if schedule.handler in parsed:
            raise ValueError("Schedule policies must have unique handlers per scope.")
        parsed[schedule.handler] = schedule
    return parsed


class ScheduleConfig(SchedulePolicy):
    id: str = Field(
        default_factory=lambda: uuid4().hex, regex=r"^[A-Za-z0-9_.:-]{1,128}$"
    )
    payload_json: str = Field(default="{}", max_length=8192)
    enabled: bool = True

    @validator("payload_json")
    def validate_payload(cls, value: str) -> str:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("Schedule payload must be a JSON object.")
        # Escape HTML-sensitive characters before the database's generic string
        # sanitization; decoding the JSON must preserve the caller's data.
        value = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        for character in "<>&":
            value = value.replace(character, f"\\u{ord(character):04x}")
        if len(value.encode()) > 8192:
            raise ValueError("Schedule payload must not exceed 8192 bytes.")
        return value


class ScheduledJob(ScheduleConfig):
    namespace: str
    user_id: str | None = None
    next_run_at: int | None = None
    lease_token: str | None = None
    lease_until: int = 0

    def public_data(self) -> dict:
        return self.dict(exclude={"namespace", "user_id", "lease_token", "lease_until"})


class ScheduledJobSummary(BaseModel):
    id: str
    namespace: str
    handler: str
    scope: Literal["core", "extension", "user"]
    cron_expression: str
    timezone: str
    enabled: bool
    next_run_at: int | None = None


class ScheduledJobFilters(FilterModel):
    __search_fields__ = ["id", "namespace", "handler"]
    __sort_fields__ = ["id", "namespace", "handler", "scope", "enabled", "next_run_at"]

    namespace: str | None = None
    handler: str | None = None
    enabled: bool | None = None
    scope: Literal["core", "extension", "user"] | None = None
