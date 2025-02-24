import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import uvloop
from asgi_lifespan import LifespanManager
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from lnbits.app import create_app
from lnbits.core.crud import (
    create_wallet,
    delete_account,
    get_account_by_username,
    get_payment,
    update_payment,
)
from lnbits.core.models import Account, CreateInvoice, PaymentState, User
from lnbits.core.models.users import UpdateSuperuserPassword
from lnbits.core.services import create_user_account, update_wallet_balance
from lnbits.core.views.auth_api import first_install
from lnbits.core.views.payment_api import _api_payments_create_invoice
from lnbits.db import DB_TYPE, SQLITE, Database
from lnbits.settings import AuthMethods, Settings
from lnbits.settings import settings as lnbits_settings
from lnbits.wallets.fake import FakeWallet
from tests.helpers import (
    get_random_invoice_data,
)

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def settings():
    # override settings for tests
    lnbits_settings.lnbits_admin_extensions = []
    lnbits_settings.lnbits_data_folder = "./tests/data"
    lnbits_settings.lnbits_admin_ui = True
    lnbits_settings.lnbits_extensions_default_install = []
    lnbits_settings.lnbits_extensions_deactivate_all = True

    yield lnbits_settings


@pytest.fixture(autouse=True)
def run_before_and_after_tests(settings: Settings):
    """Fixture to execute asserts before and after a test is run"""
    _settings_cleanup(settings)
    yield  # this is where the testing happens
    _settings_cleanup(settings)


# use session scope to run once before and once after all tests
@pytest.fixture(scope="session")
async def app(settings: Settings):
    app = create_app()
    async with LifespanManager(app) as manager:
        settings.first_install = True
        await first_install(
            UpdateSuperuserPassword(
                username="superadmin",
                password="secret1234",
                password_repeat="secret1234",
            )
        )

        yield manager.app


@pytest.fixture(scope="session")
async def client(app, settings: Settings):
    url = f"http://{settings.host}:{settings.port}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=url) as client:
        yield client


# function scope
@pytest.fixture(scope="function")
async def http_client(app, settings: Settings):
    url = f"http://{settings.host}:{settings.port}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=url) as client:
        yield client


@pytest.fixture(scope="session")
def test_client(app):
    return TestClient(app)


@pytest.fixture(scope="session")
async def db():
    yield Database("database")


@pytest.fixture(scope="session")
async def user_alan():
    account = await get_account_by_username("alan")
    if account:
        await delete_account(account.id)

    account = Account(
        id=uuid4().hex,
        email="alan@lnbits.com",
        username="alan",
    )
    account.hash_password("secret1234")
    user = await create_user_account(account)

    yield user


@pytest.fixture(scope="session")
async def from_user():
    user = await create_user_account()
    yield user


@pytest.fixture(scope="session")
async def from_wallet(from_user):
    user = from_user

    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet_from")
    await update_wallet_balance(
        wallet=wallet,
        amount=999999999,
    )
    yield wallet


@pytest.fixture(scope="session")
async def to_wallet_pagination_tests(to_user):
    user = to_user
    wallet = await create_wallet(
        user_id=user.id, wallet_name="test_wallet_to_pagination_tests"
    )
    yield wallet


@pytest.fixture
async def from_wallet_ws(from_wallet, test_client):
    # wait a bit in order to avoid receiving change_balance notification
    await asyncio.sleep(0.1)
    with test_client.websocket_connect(f"/api/v1/ws/{from_wallet.inkey}") as ws:
        yield ws


@pytest.fixture(scope="session")
async def to_user():
    user = await create_user_account()
    yield user


@pytest.fixture(scope="session")
async def superuser_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth", json={"username": "superadmin", "password": "secret1234"}
    )
    client.cookies.clear()

    yield response.json().get("access_token")


@pytest.fixture(scope="session")
async def to_wallet(to_user):
    user = to_user
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet_to")
    await update_wallet_balance(
        wallet=wallet,
        amount=999999999,
    )
    yield wallet


@pytest.fixture(scope="session")
async def to_fresh_wallet(to_user):
    user = to_user
    wallet = await create_wallet(user_id=user.id, wallet_name="test_wallet_to_fresh")
    yield wallet


@pytest.fixture
async def to_wallet_ws(to_wallet, test_client):
    # wait a bit in order to avoid receiving change_balance notification
    await asyncio.sleep(0.1)
    with test_client.websocket_connect(f"/api/v1/ws/{to_wallet.inkey}") as ws:
        yield ws


@pytest.fixture(scope="session")
async def inkey_fresh_headers_to(to_fresh_wallet):
    wallet = to_fresh_wallet
    yield {
        "X-Api-Key": wallet.inkey,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="session")
async def inkey_headers_from(from_wallet):
    wallet = from_wallet
    yield {
        "X-Api-Key": wallet.inkey,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="session")
async def adminkey_headers_from(from_wallet):
    wallet = from_wallet
    yield {
        "X-Api-Key": wallet.adminkey,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="session")
async def user_headers_from(client: AsyncClient, from_user: User):
    response = await client.post("/api/v1/auth/usr", json={"usr": from_user.id})
    client.cookies.clear()

    access_token = response.json().get("access_token")
    yield {
        "Authorization": "Bearer " + access_token,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="session")
async def inkey_headers_to(to_wallet):
    wallet = to_wallet
    yield {
        "X-Api-Key": wallet.inkey,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="session")
async def adminkey_headers_to(to_wallet):
    wallet = to_wallet
    yield {
        "X-Api-Key": wallet.adminkey,
        "Content-type": "application/json",
    }


@pytest.fixture(scope="session")
async def invoice(to_wallet):
    data = await get_random_invoice_data()
    invoice_data = CreateInvoice(**data)
    invoice = await _api_payments_create_invoice(invoice_data, to_wallet)
    yield invoice
    del invoice


@pytest.fixture(scope="function")
async def external_funding_source():
    yield FakeWallet()


@pytest.fixture(scope="session")
async def fake_payments(client, inkey_fresh_headers_to):

    ts = datetime.now(timezone.utc).timestamp()

    # Because sqlite only stores timestamps with milliseconds
    # we have to wait a second to ensure a different timestamp than previous invoices
    if DB_TYPE == SQLITE:
        await asyncio.sleep(1)

    fake_data = [
        CreateInvoice(amount=10, memo="xxxx", out=False),
        CreateInvoice(amount=100, memo="yyyy", out=False),
        CreateInvoice(amount=1000, memo="xxyy", out=False),
    ]

    for invoice in fake_data:
        response = await client.post(
            "/api/v1/payments", headers=inkey_fresh_headers_to, json=invoice.dict()
        )
        assert response.is_success
        data = response.json()
        assert data["checking_id"]
        payment = await get_payment(data["checking_id"])
        payment.status = PaymentState.SUCCESS
        await update_payment(payment)

    params = {
        "created_at[ge]": ts,
        "created_at[le]": datetime.now(timezone.utc).timestamp(),
    }
    return fake_data, params


def _settings_cleanup(settings: Settings):
    settings.lnbits_allow_new_accounts = True
    settings.lnbits_allowed_users = []
    settings.auth_allowed_methods = AuthMethods.all()
    settings.auth_credetials_update_threshold = 120
    settings.lnbits_reserve_fee_percent = 1
    settings.lnbits_reserve_fee_min = 2000
    settings.lnbits_service_fee = 0
    settings.lnbits_wallet_limit_daily_max_withdraw = 0
    settings.lnbits_admin_extensions = []
    settings.lnbits_admin_users = []
    settings.lnbits_max_outgoing_payment_amount_sats = 10_000_000_100
    settings.lnbits_max_incoming_payment_amount_sats = 10_000_000_200
