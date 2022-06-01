import asyncio
import pytest
from httpx import AsyncClient
from lnbits.app import create_app
from lnbits.commands import migrate_databases
from lnbits.settings import HOST, PORT
import tests.mocks

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
