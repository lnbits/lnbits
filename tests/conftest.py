import asyncio
import pytest_asyncio

from httpx import AsyncClient
from lnbits.app import create_app
from lnbits.commands import migrate_databases
from lnbits.settings import HOST, PORT

from lnbits.core.views.api import api_payments_create_invoice, CreateInvoiceData

from lnbits.core.crud import create_account, create_wallet, get_wallet
from tests.helpers import credit_wallet, get_random_invoice_data

from lnbits.db import Database
from lnbits.core.models import User, Wallet, Payment, BalanceCheck
from typing import Tuple


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


# use session scope to run once before and once after all tests
@pytest_asyncio.fixture(scope="session")
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


@pytest_asyncio.fixture(scope="session")
async def client(app):
    client = AsyncClient(app=app, base_url=f"http://{HOST}:{PORT}")
    yield client
    await client.aclose()


@pytest_asyncio.fixture(scope="session")
async def db():
    yield Database("database")


@pytest_asyncio.fixture(scope="session")
async def from_user():
    user = await create_account()
    yield user


@pytest_asyncio.fixture(scope="session")
async def from_wallet(from_user):
    user = from_user
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet_from")
    await credit_wallet(
        wallet_id=wallet.id,
        amount=99999999,
    )
    yield wallet


@pytest_asyncio.fixture(scope="session")
async def to_user():
    user = await create_account()
    yield user


@pytest_asyncio.fixture(scope="session")
async def to_wallet(to_user):
    user = to_user
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet_to")
    await credit_wallet(
        wallet_id=wallet.id,
        amount=99999999,
    )
    yield wallet


@pytest_asyncio.fixture(scope="session")
async def inkey_headers_from(from_wallet):
    wallet = from_wallet
    yield {
        "X-Api-Key": wallet.inkey,
        "Content-type": "application/json",
    }


@pytest_asyncio.fixture(scope="session")
async def adminkey_headers_from(from_wallet):
    wallet = from_wallet
    yield {
        "X-Api-Key": wallet.adminkey,
        "Content-type": "application/json",
    }


@pytest_asyncio.fixture(scope="session")
async def inkey_headers_to(to_wallet):
    wallet = to_wallet
    yield {
        "X-Api-Key": wallet.inkey,
        "Content-type": "application/json",
    }


@pytest_asyncio.fixture(scope="session")
async def adminkey_headers_to(to_wallet):
    wallet = to_wallet
    yield {
        "X-Api-Key": wallet.adminkey,
        "Content-type": "application/json",
    }


@pytest_asyncio.fixture(scope="session")
async def invoice(to_wallet):
    wallet = to_wallet
    data = await get_random_invoice_data()
    invoiceData = CreateInvoiceData(**data)
    stuff_lock = asyncio.Lock()
    async with stuff_lock:
        invoice = await api_payments_create_invoice(invoiceData, wallet)
    await asyncio.sleep(1)
    yield invoice
    del invoice
