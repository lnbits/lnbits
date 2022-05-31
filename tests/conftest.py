import pytest

from lnbits.app import create_app


@pytest.fixture
async def client():
    app = create_app()
    app.config["TESTING"] = True

    async with app.test_client() as client:
        yield client
