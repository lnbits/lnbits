# ruff: noqa: E402
import asyncio
from time import time

import uvloop

uvloop.install()

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

from lnbits.app import create_app
from lnbits.core.crud import (
    create_account,
    create_wallet,
    get_user,
    update_payment_status,
)
from lnbits.core.models import CreateInvoice
from lnbits.core.services import update_wallet_balance
from lnbits.core.views.payment_api import api_payments_create_invoice
from lnbits.db import DB_TYPE, SQLITE, Database
from lnbits.settings import settings
from tests.helpers import (
    clean_database,
    get_hold_invoice,
    get_random_invoice_data,
    get_real_invoice,
)

# override settings for tests
settings.lnbits_admin_extensions = []
settings.lnbits_data_folder = "./tests/data"
settings.lnbits_admin_ui = True
settings.lnbits_extensions_default_install = []


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


# use session scope to run once before and once after all tests
@pytest_asyncio.fixture(scope="session")
async def app():
    clean_database(settings)
    app = create_app()
    await app.router.startup()
    settings.first_install = False
    yield app
    await app.router.shutdown()


@pytest_asyncio.fixture(scope="session")
async def client(app):
    client = AsyncClient(app=app, base_url=f"http://{settings.host}:{settings.port}")
    yield client
    await client.aclose()


@pytest.fixture(scope="session")
def test_client(app):
    return TestClient(app)


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
    await update_wallet_balance(
        wallet_id=wallet.id,
        amount=999999999,
    )
    yield wallet


@pytest_asyncio.fixture
async def from_wallet_ws(from_wallet, test_client):
    # wait a bit in order to avoid receiving topup notification
    await asyncio.sleep(0.1)
    with test_client.websocket_connect(f"/api/v1/ws/{from_wallet.id}") as ws:
        yield ws


@pytest_asyncio.fixture(scope="session")
async def to_user():
    user = await create_account()
    yield user


@pytest.fixture()
def from_super_user(from_user):
    prev = settings.super_user
    settings.super_user = from_user.id
    yield from_user
    settings.super_user = prev


@pytest_asyncio.fixture(scope="session")
async def superuser():
    user = await get_user(settings.super_user)
    yield user


@pytest_asyncio.fixture(scope="session")
async def to_wallet(to_user):
    user = to_user
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet_to")
    await update_wallet_balance(
        wallet_id=wallet.id,
        amount=999999999,
    )
    yield wallet


@pytest_asyncio.fixture
async def to_wallet_ws(to_wallet, test_client):
    # wait a bit in order to avoid receiving topup notification
    await asyncio.sleep(0.1)
    with test_client.websocket_connect(f"/api/v1/ws/{to_wallet.id}") as ws:
        yield ws


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
    invoiceData = CreateInvoice(**data)
    invoice = await api_payments_create_invoice(invoiceData, to_wallet)
    yield invoice
    del invoice


@pytest_asyncio.fixture(scope="function")
async def real_invoice():
    invoice = get_real_invoice(100)
    yield {"bolt11": invoice["payment_request"]}
    del invoice


@pytest_asyncio.fixture(scope="session")
async def fake_payments(client, adminkey_headers_from):
    # Because sqlite only stores timestamps with milliseconds
    # we have to wait a second to ensure a different timestamp than previous invoices
    if DB_TYPE == SQLITE:
        await asyncio.sleep(1)
    ts = time()

    fake_data = [
        CreateInvoice(amount=10, memo="aaaa", out=False),
        CreateInvoice(amount=100, memo="bbbb", out=False),
        CreateInvoice(amount=1000, memo="aabb", out=False),
    ]

    for invoice in fake_data:
        response = await client.post(
            "/api/v1/payments", headers=adminkey_headers_from, json=invoice.dict()
        )
        assert response.is_success
        await update_payment_status(response.json()["checking_id"], pending=False)

    params = {"time[ge]": ts, "time[le]": time()}
    return fake_data, params


@pytest_asyncio.fixture(scope="function")
async def hold_invoice():
    invoice = get_hold_invoice(100)
    yield invoice
    del invoice
