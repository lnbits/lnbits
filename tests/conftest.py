import asyncio

import pytest_asyncio
from httpx import AsyncClient

from lnbits.app import create_app
from lnbits.commands import migrate_databases
from lnbits.core.crud import create_account, create_wallet
from lnbits.core.views.api import CreateInvoiceData, api_payments_create_invoice
from lnbits.db import Database
from lnbits.settings import HOST, PORT
from tests.helpers import credit_wallet, get_random_invoice_data


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


# use session scope to run once before and once after all tests
@pytest_asyncio.fixture(scope="session")
async def app():
    app = create_app()
    await migrate_databases()
    yield app


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
    data = await get_random_invoice_data()
    invoiceData = CreateInvoiceData(**data)
    invoice = await api_payments_create_invoice(invoiceData, to_wallet)
    yield invoice
    del invoice
