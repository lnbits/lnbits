import asyncio
from .models import *


class Storage:
    """ Manages persistent db storage (read/write). """

    async def read_schedule_entries(self):
        pass
    async def create_schedule_entry(self, entry: ScheduleEntry):
        pass
    async def delete_schedule_entry(self, id: int):
        pass

    async def read_payment_count(self, schedule_id):
        pass
    async def read_payment_log_entries(self, schedule_id):
        pass
    async def create_payment_log(self, entry: PaymentLogEntry):
        pass


class InMemoryStorage(Storage):
    def __init__(self):
        self.schedule = []
        self.payments = []
        self._last_id = 0

    @asyncio.coroutine
    def read_schedule_entries(self):
        return self.schedule

    async def read_payment_count(self, schedule_id):
        return len(await self.read_payment_log_entries(schedule_id))

    @asyncio.coroutine
    def read_payment_log_entries(self, schedule_id):
        return [p for p in self.payments if p.schedule_id == schedule_id]

    def _inc_id(self, entry: NamedTuple):
        self._last_id += 1
        return entry._replace(id=self._last_id)

    @asyncio.coroutine
    def create_schedule_entry(self, entry: ScheduleEntry):
        self.schedule.append(self._inc_id(entry))

    @asyncio.coroutine
    def create_payment_log(self, entry: PaymentLogEntry):
        self.payments.append(self._inc_id(entry))

    @asyncio.coroutine
    def delete_schedule_entry(self, id: int):
        self.schedule = [s for s in self.schedule if s.id != id]


def row_to_ScheduleEntry(row):
    l = list(row[:-2])
    l[3] = datetime.fromtimestamp(l[3])
    return ScheduleEntry(*l)


class SqliteStorage(Storage):
    def __init__(self, db):
        self._db = db

    async def read_schedule_entries(self):
        rows = await self._db.fetchall(
            """
            SELECT *
            FROM autopay.schedule_entries
            WHERE is_deleted = ?
            """,
            (0,),
        )
        return [row_to_ScheduleEntry(r) for r in rows]

    async def create_schedule_entry(self, entry: ScheduleEntry):
        await self._db.execute(
            """
            INSERT INTO autopay.schedule_entries (wallet_id, title, base_datetime, repeat_freq, lnurl, amount_msat)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entry.wallet_id, entry.title, datetime.timestamp(entry.base_datetime), entry.repeat_freq, entry.lnurl, entry.amount_msat)
        )

    async def delete_schedule_entry(self, id: int):
        await self._db.execute(
            """
            UPDATE autopay.schedule_entries
            SET is_deleted = 1
            WHERE id = ?
            """,
            (id,)
        )

    async def read_payment_count(self, schedule_id):
        row = await self._db.fetchone(
            """
            SELECT COUNT(*)
            FROM autopay.payment_log
            WHERE schedule_id = ?
            """,
            (schedule_id,)
        )
        return row[0]

    async def read_payment_log_entries(self, schedule_id):
        rows = await self._db.fetchall(
            """
            SELECT *
            FROM autopay.payment_log
            WHERE schedule_id = ?
            """,
            (schedule_id,))
        return [PaymentLogEntry(*r) for r in rows]

    async def create_payment_log(self, entry: PaymentLogEntry):
        await self._db.execute(
            """
            INSERT INTO autopay.payment_log (schedule_id, payment_hash)
            VALUES (?, ?)
            """,
            (entry.schedule_id, entry.payment_hash)
        )
