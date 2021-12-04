from typing import NamedTuple, Optional, Dict
from sqlite3 import Row

from datetime import datetime, timedelta


BASE_DT_FORMAT = "%Y-%m-%d %H:%M"
REPEAT_FREQ_OPTIONS = ["hour", "day", "week"]

class ScheduleEntry(NamedTuple):
    id: int
    wallet_id: str
    title: str
    base_datetime: datetime
    repeat_freq: str  # enum
    lnurl: str
    amount_msat: int

    def next_run(self, already_executed_count=0):
        # NOTE: doesn't handle daylight saving bullshits
        if self.repeat_freq == "hour":
            td = timedelta(hours=already_executed_count)
        elif self.repeat_freq == "day":
            td = timedelta(days=already_executed_count)
        elif self.repeat_freq == "week":
            td = timedelta(weeks=already_executed_count)
        else:
            raise ValueError(f"Unsupported repeat_freq: {self.repeat_freq}")

        return self.base_datetime + td

    @classmethod
    def from_request(cls, data: dict, validator=None):

        dt = datetime.strptime(data["base_datetime"], BASE_DT_FORMAT)

        return cls(0, data["wallet_id"],
            data["title"], dt, data["repeat_freq"], data["lnurl"], data["amount_msat"])

    @classmethod
    def validate_base_datetime(cls, base_dt: str, errors):
        try:
            dt = datetime.strptime(base_dt, BASE_DT_FORMAT)
        except ValueError as e:
            errors.append(f"'base_datetime' not in expected format: {e}")
            return False

        if dt <= datetime.now():
            errors.append(f"'base_datetime' must be in the future.")
            return False

        return True

    @classmethod
    def validate_repeat_freq(cls, repeat_freq: str, errors):
        if repeat_freq not in REPEAT_FREQ_OPTIONS:
            errors.append(f"'repeat_freq' must be one of {REPEAT_FREQ_OPTIONS}, but got {repeat_freq}.")
            return False
        return True


class PaymentLogEntry(NamedTuple):
    id: int
    schedule_id: int
    created_at: int # timestamp
    payment_hash: str
