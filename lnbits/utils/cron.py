import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from croniter import CroniterBadDateError, croniter


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
