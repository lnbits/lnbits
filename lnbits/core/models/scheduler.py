import json
import re
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from croniter import CroniterBadDateError, croniter
from pydantic import BaseModel, Field, validator


def normalize_cron(expression: str) -> str:
    """Accept minute-resolution cron, with a deliberately small grammar."""
    fields = expression.upper().split()
    if len(fields) != 5:
        raise ValueError(
            "A schedule requires five cron fields, without seconds or year."
        )
    for index, field in enumerate(fields):
        if field == "?" and index in (2, 4):
            fields[index] = "*"
            continue
        # Replace only complete month/weekday names, never arbitrary letters.
        names = (
            "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
            if index == 3
            else "SUN MON TUE WED THU FRI SAT".split() if index == 4 else []
        )
        numeric = field
        for name in names:
            numeric = numeric.replace(name, "0")
        if not re.fullmatch(r"[0-9*,/\-]+", numeric):
            raise ValueError(
                "Unsupported cron syntax. Use numbers, names, *, -, / or ,."
            )
    normalized = " ".join(fields)
    if not croniter.is_valid(normalized):
        raise ValueError("Invalid cron expression.")
    return normalized


def next_run_at(expression: str, zone: str, after: int) -> int | None:
    """Return the next UTC timestamp strictly after `after`."""
    start = datetime.fromtimestamp(after, timezone.utc).astimezone(ZoneInfo(zone))
    try:
        result = croniter(
            normalize_cron(expression), start, max_years_between_matches=8
        ).get_next(datetime)
    except CroniterBadDateError:
        return None
    return int(result.timestamp())


class ScheduleConfig(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex, regex=r"^[A-Za-z0-9_.:-]{1,128}$"
    )
    handler: str = Field(..., regex=r"^[A-Za-z0-9_-]{1,128}$")
    cron_expression: str = Field(..., min_length=1, max_length=256)
    timezone: str = Field(default="UTC", max_length=128)
    payload_json: str = Field(default="{}", max_length=8192)
    enabled: bool = True

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
