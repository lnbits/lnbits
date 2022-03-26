import asyncio
import pytest
from httpx import AsyncClient
from lnbits.app import create_app
from lnbits.commands import migrate_databases
from lnbits.settings import HOST, PORT

from lnbits.core.views.api import api_payments_create_invoice, CreateInvoiceData

from lnbits.core.crud import create_account, create_wallet, get_wallet
from tests.helpers import credit_wallet

from tests.core.views.test_api import test_core_create_invoice
from lnbits.db import Database
from lnbits.core.models import User, Wallet, Payment, BalanceCheck
from typing import Tuple


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


# use session scope to run once before and once after all tests
@pytest.fixture(scope="session")
def app(event_loop):
    app = create_app()
    # use redefined version of the event loop for scope="session"
    # loop = asyncio.get_event_loop()
    loop = event_loop
    loop.run_until_complete(migrate_databases())
    yield app
    # # get the current event loop and gracefully stop any running tasks
    # loop = event_loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    # loop.close()


@pytest.fixture(scope="session")
async def client(app):
    client = AsyncClient(app=app, base_url=f"http://{HOST}:{PORT}")
    yield client
    await client.aclose()


@pytest.fixture(scope="function")
async def db():
    yield Database("database")


# @pytest.fixture(scope="session")
# async def conn(db):
#     yield db.connect()


@pytest.fixture(scope="function")
async def user_wallet(app, client):
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet")
    print("new wallet:", wallet.id)
    await credit_wallet(
        wallet_id=wallet.id,
        amount=100000,
    )
    yield user, wallet


@pytest.fixture(scope="function")
async def inkey_headers(user_wallet):
    _, wallet = user_wallet
    yield {
        "X-Api-Key": wallet.inkey,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="function")
async def adminkey_headers(user_wallet):
    _, wallet = user_wallet
    yield {
        "X-Api-Key": wallet.adminkey,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="function")
async def invoice(user_wallet):
    _, wallet = user_wallet
    # invoice = await test_core_create_invoice(client, inkey_headers)
    data = {"out": False, "amount": 1000, "memo": "test_memo"}
    invoiceData = CreateInvoiceData(**data)
    invoice = await api_payments_create_invoice(invoiceData, wallet)
    invoice["inkey"] = wallet.inkey
    yield invoice
    del invoice
