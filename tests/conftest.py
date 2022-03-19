import asyncio
import pytest
from httpx import AsyncClient
from lnbits.app import create_app
from lnbits.commands import migrate_databases
from lnbits.settings import HOST, PORT
import tests.mocks

from lnbits.core.crud import create_account, create_wallet, get_wallet
from tests.helpers import credit_wallet

from tests.core.views.test_generic import test_core_create_invoice

# use session scope to run once before and once after all tests
@pytest.fixture(scope="session")
def app():
    # yield and pass the app to the test
    app = create_app()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(migrate_databases())
    yield app
    # get the current event loop and gracefully stop any running tasks
    loop = asyncio.get_event_loop()
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@pytest.fixture
async def client(app):
    client = AsyncClient(app=app, base_url=f"http://{HOST}:{PORT}")
    # yield and pass the client to the test
    yield client
    # close the async client after the test has finished
    await client.aclose()


@pytest.fixture
async def user_wallet():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet")
    await credit_wallet(
        wallet_id=wallet.id,
        amount=100000,
    )
    yield user, wallet


@pytest.fixture
async def inkey_headers(user_wallet):
    _, wallet = user_wallet
    yield {
        "X-Api-Key": wallet.inkey,
        "Content-type": "application/json",
    }


@pytest.fixture
async def adminkey_headers(user_wallet):
    _, wallet = user_wallet
    yield {
        "X-Api-Key": wallet.adminkey,
        "Content-type": "application/json",
    }


@pytest.fixture
async def invoice(client, inkey_headers):
    invoice = await test_core_create_invoice(client, inkey_headers)
    yield invoice
