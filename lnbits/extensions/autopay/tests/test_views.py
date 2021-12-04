import pytest
import json

from datetime import datetime, timedelta

from lnbits.app import create_app
from lnbits.extensions.autopay import context as autopay_context
from lnbits.extensions.autopay.storage import InMemoryStorage
from lnbits.extensions.autopay.utils import lnurl_scan as real_lnurl_scan


def mock_lnurl_scan(returns={"minSendable": 1, "maxSendable": 100000}):
    async def mock_lnurl_scan_(code): return returns
    return mock_lnurl_scan_


@pytest.fixture
async def client():
    # register routes, otherwise they are not loaded during pytest
    from lnbits.extensions.autopay.views_api import api_autopay_schedule_get

    app = create_app()
    app.config["TESTING"] = True

    async with app.test_client() as client:
        client.preserve_context = False
        yield client


@pytest.fixture
def context():
    c = autopay_context
    # Each test gets fresh storage
    c.storage = InMemoryStorage()
    c.lnurl_scan = mock_lnurl_scan()
    return c


def valid_schedule_data():
    future_dt = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    return {"title": "Foo", "wallet_id": "TBD", "base_datetime": future_dt, "repeat_freq": "hour", "lnurl": "dummy", "amount_msat": 2000}


async def test_api_get_schedule(client, context):
    from lnbits.extensions.autopay.models import ScheduleEntry, PaymentLogEntry

    s = context.storage
    await s.create_schedule_entry(ScheduleEntry(1, "dummywallet1", "title1", datetime.now(), "week", "urlcode", 2000))
    await s.create_payment_log(PaymentLogEntry(0, 1, 123, "h"))
    await s.create_payment_log(PaymentLogEntry(1, 1, 123, "h"))

    r = await client.get("/autopay/api/v1/schedule")
    rr = await r.get_data()
    d = json.loads(rr)

    assert "schedule" in d
    assert len(d["schedule"]) == 1
    assert d["schedule"][0]["wallet_id"] == "dummywallet1"
    assert d["schedule"][0]["amount_msat"] == 2000

    assert len(d["schedule"][0]["payments"]) == 2
    assert d["schedule"][0]["payments"][0]["payment_hash"] == "h"
    assert "next_payment" in d["schedule"][0]


async def test_api_post_schedule(client, context):
    new_schedule = valid_schedule_data()
    r = await client.post("/autopay/api/v1/schedule", json=new_schedule)
    d = json.loads(await r.get_data())
    assert r.status_code == 201
    assert len(await context.storage.read_schedule_entries()) == 1


async def test_api_post_schedule_validation(client, context):
    async def create(new_schedule):
        r = await client.post("/autopay/api/v1/schedule", json=new_schedule)
        d = json.loads(await r.get_data())
        return r.status_code, d

    # Valid
    s = valid_schedule_data()
    code, data = await create(s)
    assert code == 201

    # Missing title
    s = valid_schedule_data()
    s["title"] = None
    code, data = await create(s)
    assert code == 400
    assert "title" in data["message"]

    # Invalid repaet freq
    s = valid_schedule_data()
    s["repeat_freq"] = "invalid"
    code, data = await create(s)
    assert code == 400
    assert "repeat_freq" in data["message"]

    # Incorrect base_datetime format
    s = valid_schedule_data()
    s["base_datetime"] = "foo"
    code, data = await create(s)
    assert code == 400
    assert "base_datetime" in data["message"]

    # Not future datetime
    dt = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    s = valid_schedule_data()
    s["base_datetime"] = dt
    code, data = await create(s)
    assert code == 400
    assert "base_datetime" in data["message"]

    # Missing amount
    s = valid_schedule_data()
    s["amount_msat"] = None
    code, data = await create(s)
    assert code == 400
    assert "amount_msat" in data["message"]

    # Amount not within min/max from lnurl
    context.lnurl_scan = mock_lnurl_scan({"minSendable": 10000, "maxSendable": 200000})
    s = valid_schedule_data()
    s["amount_msat"] = 100  # too small
    code, data = await create(s)
    assert code == 400
    assert "amount_msat" in data["message"]

    s = valid_schedule_data()
    s["amount_msat"] = 200001  # too large
    code, data = await create(s)
    assert code == 400
    assert "amount_msat" in data["message"]

    # Amount within - valid
    s = valid_schedule_data()
    s["amount_msat"] = 10000
    code, data = await create(s)
    assert code == 201

    # Invalid lnurl code
    context.lnurl_scan = real_lnurl_scan
    s = valid_schedule_data()
    s["lnurl"] = "invalid"
    code, data = await create(s)
    assert code == 400
    assert "lnurl" in data["message"]


async def test_api_post_delete_schedule(client, context):
    # Create new schedule entry
    new_schedule = valid_schedule_data()
    r = await client.post("/autopay/api/v1/schedule", json=new_schedule)
    d = json.loads(await r.get_data())
    assert r.status_code == 201

    # Test it's there through API
    r = await client.get("/autopay/api/v1/schedule")
    d = json.loads(await r.get_data())
    assert "schedule" in d
    assert len(d["schedule"]) == 1

    # Delete it
    schedule_id = d["schedule"][0]["id"]
    r = await client.delete(f"/autopay/api/v1/schedule/{schedule_id}")
    d = json.loads(await r.get_data())
    assert r.status_code == 200
    assert len(await context.storage.read_schedule_entries()) == 0


async def test_api_scheduler(client, context):
    r = await client.post("/autopay/api/v1/scheduler")
    # d = json.loads(await r.get_data())
    assert r.status_code == 200
