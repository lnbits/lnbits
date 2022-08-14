import pytest
import pytest_asyncio
from loguru import logger

from lnbits.core.crud import get_wallet
from tests.conftest import adminkey_headers_from, client, invoice
from tests.extensions.scheduledpayments.conftest import (
    recurring_schedule_payment,
    scheduledpayments_wallet,
)
from tests.helpers import credit_wallet
from tests.mocks import WALLET


@pytest.mark.asyncio
async def test_schedules_unknown_schedule(client):
    response = await client.get("/scheduledpayments/api/v1/schedule/u")
    assert response.json() == {"detail": "Schedule does not exist."}


@pytest.mark.asyncio
async def test_scheduledpayments_api_create_schedule_valid(
    client, scheduledpayments_wallet
):
    query = {
        "wallet": scheduledpayments_wallet.id,
        "recipient": "lee@pay.bitcoinjungle.app",
        "famount": 0.01,
        "currency": "USD",
        "interval": "* * * * *",
        "timezone": "UTC",
        "start_date": None,
        "end_date": None,
    }

    famount = query["famount"]
    recipient = query["recipient"]
    currency = query["currency"]
    interval = query["interval"]
    timezone = query["timezone"]

    response = await client.post(
        "/scheduledpayments/api/v1/schedule",
        json=query,
        headers={"X-Api-Key": scheduledpayments_wallet.inkey},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["famount"] == famount * 100
    assert data["recipient"] == recipient
    assert data["currency"] == currency
    assert data["interval"] == interval
    assert data["timezone"] == timezone
    assert data["start_date"] == None
    assert data["end_date"] == None
