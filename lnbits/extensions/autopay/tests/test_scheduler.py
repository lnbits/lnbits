from lnbits.extensions.autopay.scheduler import *
from lnbits.extensions.autopay.storage import InMemoryStorage
from lnbits.extensions.autopay.models import *

from datetime import datetime


class MockPaymentExecutor:
    def __init__(self):
        self.calls = []

    async def __call__(self, *args):
        self.calls.append(args)
        return f"hash_{args}"

    def reset(self):
        self.calls = []


def dummyScheduleEntry(**kwargs):
    se = ScheduleEntry(0, "wall", "dummy", datetime.now(), "hour", "LNURL", 1000)
    return se._replace(**kwargs)


async def test_Scheduler_basics():
    st = InMemoryStorage()
    mock = MockPaymentExecutor()
    s = Scheduler(st, mock)

    # 10th October, 10am
    now_10am = datetime(2021, 10, 13, 10, 0, 0)
    await s.run(now_10am)
    assert len(st.payments) == 0
    assert len(mock.calls) == 0

    # this one runs weekly, 9am
    now_9am = datetime(2021, 10, 13, 9, 0, 0)
    se2 = dummyScheduleEntry(base_datetime=now_9am, repeat_freq="week", wallet_id="9am_wallet", amount_msat=3000)
    await st.create_schedule_entry(se2)

    now_8am = datetime(2021, 10, 13, 8, 0, 0)
    await s.run(now_8am)
    # SHOULD NOT RUN, too early
    assert len(st.payments) == 0
    assert len(mock.calls) == 0

    await s.run(now_10am)
    # SHOULD RUN
    assert len(mock.calls) == 1
    assert mock.calls[0][0] == "9am_wallet"
    assert mock.calls[0][2] == 3000
    assert len(st.payments) == 1

    mock.reset()
    await s.run(now_10am)
    # SHOULD NOT run again
    assert len(mock.calls) == 0
    assert len(st.payments) == 1

    now_nextweek = datetime(2021, 10, 20, 11, 0, 0)
    await s.run(now_nextweek)
    # SHOULD RUN
    assert len(mock.calls) == 1
    assert mock.calls[0][0] == "9am_wallet"
    assert mock.calls[0][2] == 3000
    assert len(st.payments) == 2


async def test_Scheduler_hourly():
    st = InMemoryStorage()
    mock = MockPaymentExecutor()
    s = Scheduler(st, mock)

    now_9am = datetime(2021, 10, 13, 9, 0, 0)
    se1 = dummyScheduleEntry(base_datetime=now_9am, repeat_freq="hour")
    await st.create_schedule_entry(se1)

    await s.run(datetime(2021, 10, 13, 8, 0, 0))
    assert len(st.payments) == 0
    assert len(mock.calls) == 0

    await s.run(datetime(2021, 10, 13, 9, 10, 0))
    assert len(st.payments) == 1
    assert len(mock.calls) == 1

    await s.run(datetime(2021, 10, 13, 10, 1, 0))
    assert len(st.payments) == 2
    assert len(mock.calls) == 2

    await s.run(datetime(2021, 10, 13, 10, 20, 0))
    assert len(st.payments) == 2
    assert len(mock.calls) == 2

    await s.run(datetime(2021, 10, 13, 11, 1, 0))
    assert len(st.payments) == 3
    assert len(mock.calls) == 3


async def test_Scheduler_ignores_deleted_entries():
    st = InMemoryStorage()
    mock = MockPaymentExecutor()
    s = Scheduler(st, mock)


    now_9am = datetime(2021, 10, 13, 9, 0, 0)
    now_10am = datetime(2021, 10, 13, 10, 0, 0)
    se1 = dummyScheduleEntry(base_datetime=now_9am, repeat_freq="hour")
    await st.create_schedule_entry(se1)
    se1_id = (await st.read_schedule_entries())[0].id
    assert se1_id > 0

    # SHOULD RUN
    await s.run(now_10am)
    assert len(mock.calls) == 1
    mock.reset()

    # SHOULD NOT RUN
    await st.delete_schedule_entry(se1_id)
    await s.run(now_10am)
    assert len(mock.calls) == 0
