from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from lnbits.core.crud import create_wallet, get_wallet
from lnbits.core.crud.payments import get_payments_paginated, update_payment
from lnbits.core.db import db
from lnbits.core.models.wallets import WalletType
from lnbits.core.services.payments import pay_invoice, update_wallet_balance
from lnbits.wallets.base import PaymentPendingStatus, PaymentResponse


@pytest.fixture
async def resend_api_context(app, from_user, external_funding_source, settings, mocker):
    wallet = await create_wallet(user_id=from_user.id)
    settings.lnbits_reserve_fee_min = 20_000
    await update_wallet_balance(wallet, 1_040)
    invoice = await external_funding_source.create_invoice(1_000)
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=external_funding_source,
    )
    backend = mocker.patch.object(
        external_funding_source,
        "pay_invoice",
        AsyncMock(
            return_value=PaymentResponse(checking_id=f"backend_{invoice.checking_id}")
        ),
    )
    mocker.patch.object(
        external_funding_source,
        "get_payment_status",
        AsyncMock(return_value=PaymentPendingStatus()),
    )
    notify = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background"
    )
    payment = await pay_invoice(
        wallet_id=wallet.id,
        payment_request=invoice.payment_request,
        description="Keep this memo",
        labels=["keep"],
        extra={"reference": "order-1"},
        external_id="order-1",
        webhook="https://example.com/payment",
    )
    backend.reset_mock()
    return SimpleNamespace(
        wallet=wallet, payment=payment, backend=backend, notify=notify
    )


@pytest.mark.anyio
@pytest.mark.parametrize("success", [False, True], ids=["pending", "success"])
async def test_force_resend_api_reuses_pending_payment(
    client, superuser_token, resend_api_context, success
):
    ctx = resend_api_context
    assert await _wallet_balance(ctx.wallet.id) == 20_000
    ctx.backend.return_value = PaymentResponse(
        ok=True if success else None,
        checking_id=f"resent_{ctx.payment.payment_hash}",
        fee_msat=2_000 if success else None,
    )
    response = await _resend(client, superuser_token, ctx.payment)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == ("success" if success else "pending")
    assert result["checking_id"] == f"resent_{ctx.payment.payment_hash}"
    ctx.backend.assert_awaited_once_with(ctx.payment.bolt11, 20_000)
    outgoing = await get_payments_paginated(wallet_id=ctx.wallet.id, outgoing=True)
    assert outgoing.total == 1
    stored = outgoing.data[0]
    for field in (
        "payment_hash",
        "amount",
        "memo",
        "labels",
        "extra",
        "external_id",
        "webhook",
    ):
        assert getattr(stored, field) == getattr(ctx.payment, field)
    assert await _wallet_balance(ctx.wallet.id) == 20_000 + (18_000 if success else 0)
    assert ctx.notify.call_count == int(success)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "role", ["anonymous", "owner", "admin", "admin-key", "invoice-key"]
)
async def test_force_resend_api_requires_superuser(
    client, resend_api_context, user_headers_from, admin_user, role
):
    ctx = resend_api_context
    headers = {}
    if role == "owner":
        headers = user_headers_from
    elif role == "admin":
        login = await client.post(
            "/api/v1/auth",
            json={"username": admin_user.username, "password": "secret1234"},
        )
        client.cookies.clear()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    elif role == "admin-key":
        headers = {"X-Api-Key": ctx.wallet.adminkey}
    elif role == "invoice-key":
        headers = {"X-Api-Key": ctx.wallet.inkey}
    response = await client.post(
        "/api/v1/payments/force-resend",
        headers=headers,
        json={"wallet_id": ctx.wallet.id, "checking_id": ctx.payment.checking_id},
    )
    assert response.status_code in (401, 403)
    ctx.backend.assert_not_awaited()
    ctx.notify.assert_not_called()
    assert await _wallet_balance(ctx.wallet.id) == 20_000


@pytest.mark.anyio
@pytest.mark.parametrize("wrong_field", ["wallet_id", "checking_id", "payment_hash"])
async def test_force_resend_api_requires_exact_wallet_and_checking_id(
    client, superuser_token, resend_api_context, wrong_field
):
    ctx = resend_api_context
    fields = (
        {"checking_id": ctx.payment.payment_hash}
        if wrong_field == "payment_hash"
        else {wrong_field: uuid4().hex}
    )
    response = await _resend(client, superuser_token, ctx.payment, **fields)
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment does not exist."
    ctx.backend.assert_not_awaited()
    assert await _wallet_balance(ctx.wallet.id) == 20_000


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"status": "success"}, id="successful"),
        pytest.param({"status": "failed"}, id="failed"),
        pytest.param({"amount": 1_000_000}, id="incoming"),
        pytest.param({"amount": 0}, id="zero-amount"),
        pytest.param({"checking_id": "internal_"}, id="internal"),
        pytest.param({"checking_id": "service_fee_"}, id="service-fee"),
        pytest.param({"checking_id": "temp_"}, id="temporary"),
        pytest.param({"fiat_provider": "stripe"}, id="fiat-payment"),
        pytest.param({"extra": {"hold_invoice": True}}, id="hold-invoice"),
        pytest.param({"extra": {"tag": "admin"}}, id="balance-adjustment"),
        pytest.param({"bolt11": "lno1offer"}, id="bolt12-offer"),
        pytest.param({"bolt11": "LNI1INVOICE"}, id="bolt12-invoice"),
        pytest.param({"wallet_type": WalletType.FIAT.value}, id="fiat-wallet"),
        pytest.param({"wallet_type": WalletType.ONCHAIN.value}, id="onchain-wallet"),
    ],
)
async def test_force_resend_api_rejects_ineligible_payment(
    client, superuser_token, resend_api_context, changes
):
    ctx = resend_api_context
    changes = dict(changes)
    checking_prefix = changes.pop("checking_id", None)
    wallet_type = changes.pop("wallet_type", None)
    payment = await update_payment(
        ctx.payment.copy(update=changes),
        new_checking_id=checking_prefix + uuid4().hex if checking_prefix else None,
    )
    if wallet_type:
        await db.execute(
            "UPDATE wallets SET wallet_type = :type WHERE id = :id",
            {"type": wallet_type, "id": payment.wallet_id},
        )
    response = await _resend(client, superuser_token, payment)
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Only pending outgoing external BOLT11 payments can be resent."
    )
    ctx.backend.assert_not_awaited()
    ctx.notify.assert_not_called()


async def _resend(client, token, payment, **fields):
    return await client.post(
        "/api/v1/payments/force-resend",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "wallet_id": payment.wallet_id,
            "checking_id": payment.checking_id,
            **fields,
        },
    )


async def _wallet_balance(wallet_id: str) -> int:
    wallet = await get_wallet(wallet_id)
    assert wallet is not None
    return wallet.balance_msat
