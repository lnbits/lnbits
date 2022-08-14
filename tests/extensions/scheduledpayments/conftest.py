import pytest
import pytest_asyncio

from lnbits.core.crud import create_account, create_wallet
from lnbits.extensions.scheduledpayments.crud import create_schedule
from lnbits.extensions.scheduledpayments.models import CreateScheduleData


@pytest_asyncio.fixture
async def scheduledpayments_wallet():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="scheduledpayments_test")

    return wallet


@pytest_asyncio.fixture
async def recurring_schedule_payment(scheduledpayments_wallet):
    schedule_data = CreateScheduleData(
        wallet=scheduledpayments_wallet.id,
        recipient="lee@pay.bitcoinjungle.app",
        famount=0.01,
        currency="USD",
        interval="* * * * *",
        timezone="UTC",
        start_date="2022-01-01",
        end_date="2022-12-31",
    )
    schedule = await create_schedule(
        wallet_id=scheduledpayments_wallet.id, data=schedule_data
    )

    return schedule.dict()
