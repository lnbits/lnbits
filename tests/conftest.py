import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient

from lnbits.app import check_poetry, create_app
from lnbits.commands import migrate_core_databases
from lnbits.core.crud import create_account, create_wallet
from lnbits.core.views.api import CreateInvoiceData, api_payments_create_invoice
from lnbits.db import Database
from lnbits.settings import settings
from tests.helpers import credit_wallet, get_random_invoice_data, get_real_invoice


def pytest_addoption(parser):
    parser.addoption('--extensions', action='store_true', dest="extensions",
                     default=False, help="enable extensions tests")


def pytest_configure(config: pytest.Config):
    # preserve existing markexpr
    if config.option.markexpr:
        config.option.markexpr += ' and '
    if config.option.extensions:
        config.option.markexpr += 'extensions'
    else:
        config.option.markexpr += 'not extensions'


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
    loop.run_until_complete(check_poetry())
    loop.run_until_complete(migrate_core_databases())
    yield app
    # # get the current event loop and gracefully stop any running tasks
    # loop = event_loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    # loop.close()


@pytest_asyncio.fixture(scope="session")
async def client(app):
    client = AsyncClient(app=app, base_url=f"http://{settings.host}:{settings.port}")
    yield client
    await client.aclose()


@pytest_asyncio.fixture(scope="session")
async def db():
    yield Database("database")


@pytest_asyncio.fixture(scope="session")
async def from_user():
    user = await create_account()
    yield user


@pytest_asyncio.fixture
def from_admin_user(from_user):
    """Temporarily sets the created user as the super user"""
    prev_super = settings.super_user
    settings.super_user = from_user.id
    yield from_user
    settings.super_user = prev_super


@pytest_asyncio.fixture(scope="session")
async def from_wallet(from_user):
    user = from_user
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet_from")
    await credit_wallet(
        wallet_id=wallet.id,
        amount=999999999,
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
        amount=999999999,
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


@pytest_asyncio.fixture(scope="session")
async def real_invoice():
    invoice = get_real_invoice(100_000, "test-fixture")
    yield invoice
    del invoice


@pytest_asyncio.fixture
async def installed_extension(client, from_admin_user, request):
    ext_id = request.param
    params = "?usr=" + from_admin_user.id

    response = await client.get(f"/api/v1/extension/{ext_id}/releases" + params)
    releases = response.json()
    assert len(releases) > 0

    response = await client.post(
        "/api/v1/extension" + params,
        json={"ext_id": ext_id, **releases[0]},
    )

    yield response

    if response.status_code == 200:
        response = await client.delete(f"/api/v1/extension/{ext_id}" + params)
        assert response.status_code == 200
