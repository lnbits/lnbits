from lnbits.extensions.autopay.storage import SqliteStorage, InMemoryStorage
from lnbits.extensions.autopay.models import *
from lnbits.extensions.autopay import migrations

from datetime import datetime
import re

import pytest
import asyncio
import trio


migration_fn_matcher = re.compile(r"^m(\d\d\d)_")


def create_lnbits_db(tmp_path, db_name="ext_autopay"):
    """ Monkey patch data path where the sqlite file will be created and initialize the db. """
    import lnbits.db
    _LNBITS_DATA_FOLDER = lnbits.db.LNBITS_DATA_FOLDER
    lnbits.db.LNBITS_DATA_FOLDER = tmp_path
    db = lnbits.db.Database(db_name)
    lnbits.db.LNBITS_DATA_FOLDER = _LNBITS_DATA_FOLDER
    return db


async def create_mock_sqlite_storage(tmp_path):
    """ Create dummy sqlite.db for each test. Can be configured with --basetemp pytest argument. """
    db = create_lnbits_db(tmp_path)

    # Run migrations
    for key, migrate in migrations.__dict__.items():
        match = migration_fn_matcher.match(key)
        if match: await migrate(db)

    return SqliteStorage(db)


@pytest.fixture(params=["memory", "sqlite"])
def storage(request, tmp_path):
    """ Each test with this argument will be run twice: once for InMemoryStorage, once for SqliteStorage. """
    if request.param == "memory":
        return InMemoryStorage()
    elif request.param == "sqlite":
        return trio.run(create_mock_sqlite_storage, tmp_path)


def dummyScheduleEntry(**kwargs):
    se = ScheduleEntry(0, "wall", "dummy", datetime.now(), "hour", "LNURL", 1000)
    return se._replace(**kwargs)


async def test_Storage_schedule_entries_basics(storage):
    s = storage

    assert len(await s.read_schedule_entries()) == 0

    se1 = dummyScheduleEntry()
    await s.create_schedule_entry(se1)
    assert len(await s.read_schedule_entries()) == 1

    se2 = dummyScheduleEntry()
    await s.create_schedule_entry(se2)
    assert len(await s.read_schedule_entries()) == 2


async def test_Storage_payments_basics(storage):
    s = storage

    await s.create_schedule_entry(dummyScheduleEntry())
    await s.create_schedule_entry(dummyScheduleEntry())
    se1, se2 = await s.read_schedule_entries()

    assert await s.read_payment_count(se1.id) == 0
    assert await s.read_payment_count(se2.id) == 0
    
    pe1 = PaymentLogEntry(0, se1.id, 123, "dummyhash")
    await s.create_payment_log(pe1)
    assert await s.read_payment_count(se1.id) == 1
    assert await s.read_payment_count(se2.id) == 0

    pe2 = PaymentLogEntry(0, se2.id, 124, "dummyhash2")
    await s.create_payment_log(pe2)
    assert await s.read_payment_count(se1.id) == 1
    assert await s.read_payment_count(se2.id) == 1

    pes = await s.read_payment_log_entries(se1.id)
    assert len(pes) == 1
    assert pes[0].payment_hash == "dummyhash"

    pes = await s.read_payment_log_entries(se2.id)
    assert len(pes) == 1
    assert pes[0].payment_hash == "dummyhash2"


async def test_Storage_increment_ids(storage):
    s = storage

    assert len(await s.read_schedule_entries()) == 0

    se1 = dummyScheduleEntry()
    await s.create_schedule_entry(se1)
    await s.create_schedule_entry(se1)

    ses = await s.read_schedule_entries()
    assert len(ses) == 2
    assert ses[0].id > 0
    assert ses[1].id > 0
    assert ses[0].id != ses[1].id


async def test_Storage_delete_schedule_entry(storage):
    s = storage

    se1 = dummyScheduleEntry()
    await s.create_schedule_entry(se1)
    ses = await s.read_schedule_entries()
    assert len(ses) == 1

    await s.delete_schedule_entry(ses[0].id)
    assert len(await s.read_schedule_entries()) == 0


async def test_SqliteStorage_model_types(tmp_path):
    s = await create_mock_sqlite_storage(tmp_path)

    se = dummyScheduleEntry(base_datetime=datetime(2021, 10, 13))
    await s.create_schedule_entry(se)

    ses = await s.read_schedule_entries()
    assert len(ses) == 1
    se = ses[0]

    assert type(se.base_datetime) is datetime
    assert se.base_datetime.year == 2021
    assert se.base_datetime.month == 10
    assert se.base_datetime.day == 13

    dt = se.next_run(already_executed_count=1)
    assert type(dt) is datetime
