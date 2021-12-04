from datetime import datetime

from lnbits.extensions.autopay.models import *


def test_ScheduleEntry_next_run():
    for freq in REPEAT_FREQ_OPTIONS:
        se = ScheduleEntry(0, "w", "t", datetime.now(), freq, "", 1000)
        next = se.next_run(1)
        assert next
        assert type(next) == datetime
