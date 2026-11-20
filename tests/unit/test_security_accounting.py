from importlib import import_module
from unittest.mock import AsyncMock

import pytest

from lnbits.core import migrations
from lnbits.core.crud.payments import (
    create_payment,
    get_payment,
    get_standalone_payment,
)
from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.helpers import run_migration
from lnbits.core.models import Account, CreatePayment, PaymentState
from lnbits.core.models.users import CreateUser
from lnbits.core.services import payments, users
from lnbits.core.views import user_api
from lnbits.db import DB_TYPE, SQLITE, Database
from lnbits.exceptions import PaymentError
from lnbits.wallets.base import (
    PaymentFailedStatus,
    PaymentResponse,
    PaymentSuccessStatus,
)


@pytest.fixture
async def security_db(tmp_path, settings, monkeypatch):
    if DB_TYPE != SQLITE:
        pytest.skip("temporary accounting database is SQLite-only")
    monkeypatch.setattr(settings, "lnbits_data_folder", str(tmp_path))
    monkeypatch.setattr(settings, "lnbits_user_default_extensions", [])
    db = Database("security_accounting")
    for name in (
        "crud.users",
        "crud.wallets",
        "crud.payments",
        "crud.settings",
        "crud.extensions",
        "services.users",
        "services.payments",
    ):
        monkeypatch.setattr(import_module(f"lnbits.core.{name}"), "db", db)
    try:
        async with db.connect() as conn:
            await run_migration(conn, migrations, "core")
        yield db
    finally:
        await db.engine.dispose()


@pytest.mark.anyio
async def test_closed_registration_allows_bootstrap_and_admin_invitation(
    security_db, settings
):
    assert settings.lnbits_allow_new_accounts is False
    initial = await users.init_admin_settings()
    assert initial.super_user
    assert initial.lnbits_allow_new_accounts is False
    # The admin-only provisioning handler remains usable with public registration off.
    created = await user_api.api_create_user(CreateUser(username="invited"))
    assert created.id
    assert created.password
    with pytest.raises(ValueError, match="Account creation is disabled"):
        await users.create_user_account(Account(id="b" * 32, username="uninvited"))


@pytest.mark.anyio
@pytest.mark.parametrize("later_failure", [False, True])
async def test_failed_withdrawal_releases_reserve_and_never_credits_service_fee(
    security_db, settings, monkeypatch, later_failure
):
    wallet, fee_wallet, payment = await _funded_withdrawal(settings)
    wallet = await get_wallet(wallet.id)
    assert wallet is not None
    assert wallet.balance_msat == 880000
    if later_failure:
        pending = await payments._handle_external_payment_response(
            payment, PaymentResponse(ok=None)
        )
        assert pending.pending
        fee_wallet = await get_wallet(fee_wallet.id)
        assert fee_wallet is not None
        assert fee_wallet.balance_msat == 0
        monkeypatch.setattr(
            payments,
            "check_payment_status",
            AsyncMock(return_value=PaymentFailedStatus()),
        )
        await payments.update_pending_payment(pending)
    else:
        with pytest.raises(PaymentError):
            await payments._handle_external_payment_response(
                payment, PaymentResponse(ok=False)
            )
    assert (await get_payment(payment.checking_id)).failed
    wallet = await get_wallet(wallet.id)
    fee_wallet = await get_wallet(fee_wallet.id)
    assert wallet is not None
    assert fee_wallet is not None
    assert wallet.balance_msat == 1000000
    assert fee_wallet.balance_msat == 0
    assert await get_standalone_payment(f"service_fee_{payment.payment_hash}") is None


@pytest.mark.anyio
@pytest.mark.parametrize("state", [PaymentState.PENDING, PaymentState.FAILED])
async def test_service_fee_helper_rejects_unconfirmed_payment(
    security_db, settings, state
):
    _, fee_wallet, payment = await _funded_withdrawal(settings)
    payment.status = state
    await payments._credit_service_fee_wallet(payment)
    fee_wallet = await get_wallet(fee_wallet.id)
    assert fee_wallet is not None
    assert fee_wallet.balance_msat == 0
    assert await get_standalone_payment(f"service_fee_{payment.payment_hash}") is None


@pytest.mark.anyio
async def test_confirmed_withdrawal_credits_service_fee_only_once(
    security_db, settings, monkeypatch
):
    wallet, fee_wallet, payment = await _funded_withdrawal(settings)
    monkeypatch.setattr(
        payments, "send_payment_notification_in_background", lambda *_: None
    )
    for _ in range(2):
        await payments.update_payment_success_status(
            payment, PaymentSuccessStatus(fee_msat=2000)
        )
    fee_wallet = await get_wallet(fee_wallet.id)
    wallet = await get_wallet(wallet.id)
    assert fee_wallet is not None
    assert wallet is not None
    assert fee_wallet.balance_msat == 1000
    assert wallet.balance_msat == 897000
    fee_payment = await get_standalone_payment(f"service_fee_{payment.payment_hash}")
    assert fee_payment is not None
    assert fee_payment.success
    assert fee_payment.amount == 1000


async def _funded_withdrawal(settings):
    wallet = await create_wallet(user_id="owner")
    fee_wallet = await create_wallet(user_id="fee-owner")
    settings.lnbits_service_fee_wallet = fee_wallet.id
    settings.lnbits_service_fee = 1
    settings.lnbits_service_fee_max = 0
    await create_payment(
        checking_id="funding",
        data=CreatePayment(
            wallet_id=wallet.id,
            payment_hash="f" * 64,
            bolt11="funding",
            memo="Test funding",
            amount_msat=1000000,
        ),
        status=PaymentState.SUCCESS,
    )
    payment = await create_payment(
        checking_id="withdrawal",
        data=CreatePayment(
            wallet_id=wallet.id,
            payment_hash="a" * 64,
            bolt11="withdrawal",
            memo="Test withdrawal",
            amount_msat=-100000,
            fee=-20000,
        ),
        status=PaymentState.PENDING,
    )
    return wallet, fee_wallet, payment
