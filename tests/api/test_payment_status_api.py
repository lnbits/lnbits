from hashlib import sha256
from uuid import uuid4

import pytest

from lnbits.core.crud import create_wallet, get_wallet
from lnbits.core.crud.payments import create_payment, get_payment, update_payment
from lnbits.core.models import CreatePayment, PaymentState
from lnbits.core.models.wallets import WalletType
from lnbits.task_manager import task_manager


async def status_payment(
    user, status=PaymentState.PENDING, amount=-10_000, credit=100_000
):
    wallet = await create_wallet(user_id=user.id)
    if credit:
        await create_payment(
            "internal_" + uuid4().hex,
            CreatePayment(
                wallet_id=wallet.id,
                payment_hash=uuid4().hex,
                bolt11="",
                amount_msat=credit,
                memo="Test balance",
            ),
            status=PaymentState.SUCCESS,
        )
    preimage = uuid4().hex * 2
    payment = await create_payment(
        uuid4().hex,
        CreatePayment(
            wallet_id=wallet.id,
            payment_hash=sha256(bytes.fromhex(preimage)).hexdigest(),
            bolt11="test invoice",
            amount_msat=amount,
            fee=1_000,
            memo="Status test",
            labels=["existing"],
            extra={"test": True},
            webhook="https://example.com/payment",
        ),
        status=status,
    )
    return payment, preimage


async def change_status(client, token, payment, status, **fields):
    return await client.patch(
        "/api/v1/payments/status",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "wallet_id": payment.wallet_id,
            "checking_id": payment.checking_id,
            "status": status,
            **fields,
        },
    )


@pytest.mark.anyio
@pytest.mark.parametrize("amount", [-10_000, 10_000])
@pytest.mark.parametrize(
    "old,new",
    [(old, new) for old in PaymentState for new in PaymentState if old != new],
)
async def test_change_status_all_transitions_are_silent(
    client, superuser_token, from_user, mocker, amount, old, new
):
    payment, _ = await status_payment(from_user, old, amount)
    notify = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background"
    )
    webhook = mocker.patch("lnbits.core.services.notifications.dispatch_webhook")
    backend = mocker.patch("lnbits.core.services.payments.get_funding_source")
    incoming = mocker.patch.object(task_manager.invoice_queue, "put_nowait")
    internal = mocker.patch.object(task_manager.internal_invoice_queue, "put_nowait")
    response = await change_status(client, superuser_token, payment, new)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == new
    assert result["labels"] == ["existing", "status-changed"]
    assert result["fee"] == (0 if new == PaymentState.SUCCESS else payment.fee)
    assert result["extra"] == payment.extra
    assert result["amount"] == payment.amount
    assert result["webhook"] == payment.webhook
    for side_effect in [notify, webhook, backend, incoming, internal]:
        side_effect.assert_not_called()


@pytest.mark.anyio
async def test_change_status_success_fields_and_existing_preimage(
    client, superuser_token, from_user
):
    payment, preimage = await status_payment(from_user)
    success = await change_status(
        client, superuser_token, payment, "success", fee_msat=321, preimage=preimage
    )
    assert success.status_code == 200
    assert success.json()["fee"] == -321
    assert success.json()["preimage"] == preimage
    payment = await get_payment(payment.checking_id)
    pending = await change_status(client, superuser_token, payment, "pending")
    assert pending.status_code == 200
    assert pending.json()["fee"] == -321
    payment = await get_payment(payment.checking_id)
    success = await change_status(
        client, superuser_token, payment, "success", preimage="00" * 32
    )
    assert success.status_code == 200
    assert success.json()["preimage"] == preimage
    assert success.json()["labels"].count("status-changed") == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields", [{"fee_msat": -1}, {"preimage": "invalid"}, {"preimage": "00" * 32}]
)
async def test_change_status_rejects_invalid_success_fields(
    client, superuser_token, from_user, fields
):
    payment, _ = await status_payment(from_user)
    response = await change_status(
        client, superuser_token, payment, "success", **fields
    )
    assert response.status_code == 400
    assert (await get_payment(payment.checking_id)).labels == ["existing"]


@pytest.mark.anyio
@pytest.mark.parametrize("target", [PaymentState.PENDING, PaymentState.SUCCESS])
async def test_change_status_rejects_negative_outgoing_balance(
    client, superuser_token, from_user, target
):
    payment, _ = await status_payment(from_user, PaymentState.FAILED, credit=0)
    response = await change_status(client, superuser_token, payment, target)
    assert response.status_code == 400
    assert "negative" in response.json()["detail"]
    assert (await get_payment(payment.checking_id)).failed
    wallet = await get_wallet(payment.wallet_id)
    assert wallet
    assert wallet.balance_msat == 0


@pytest.mark.anyio
@pytest.mark.parametrize("target", [PaymentState.PENDING, PaymentState.FAILED])
async def test_change_status_rejects_removing_spent_income(
    client, superuser_token, from_user, target
):
    payment, _ = await status_payment(
        from_user, PaymentState.SUCCESS, amount=10_000, credit=0
    )
    await create_payment(
        "internal_" + uuid4().hex,
        CreatePayment(
            wallet_id=payment.wallet_id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=-5_000,
            memo="Spent income",
        ),
        status=PaymentState.SUCCESS,
    )
    response = await change_status(client, superuser_token, payment, target)
    assert response.status_code == 400
    assert (await get_payment(payment.checking_id)).success


@pytest.mark.anyio
async def test_change_status_noop_and_repeated_updates(
    client, superuser_token, from_user
):
    payment, _ = await status_payment(from_user)
    noop = await change_status(client, superuser_token, payment, "pending")
    assert noop.status_code == 200
    assert noop.json()["labels"] == ["existing"]
    assert (await get_payment(payment.checking_id)).updated_at == payment.updated_at
    await change_status(client, superuser_token, payment, "success")
    changed = await change_status(client, superuser_token, payment, "failed")
    assert changed.status_code == 200
    assert changed.json()["status"] == "failed"


@pytest.mark.anyio
async def test_change_status_uses_exact_wallet_and_checking_id(
    client, superuser_token, from_user
):
    from lnbits.core.db import db

    payment, _ = await status_payment(from_user)
    other_wallet = await create_wallet(user_id=from_user.id)
    other_payment = payment.copy(update={"wallet_id": other_wallet.id})
    await db.insert("apipayments", other_payment)
    response = await change_status(client, superuser_token, payment, "success")
    assert response.status_code == 200
    untouched = await db.fetchone(
        "SELECT * FROM apipayments WHERE wallet_id = :wallet_id",
        {"wallet_id": other_wallet.id},
        type(payment),
    )
    assert untouched.pending
    assert untouched.labels == ["existing"]
    wrong_id = await change_status(
        client, superuser_token, payment, "failed", checking_id=payment.payment_hash
    )
    assert wrong_id.status_code == 404


@pytest.mark.anyio
async def test_change_status_requires_superuser(
    client, from_user, admin_user, settings
):
    payment, _ = await status_payment(from_user)
    login = await client.post(
        "/api/v1/auth", json={"username": admin_user.username, "password": "secret1234"}
    )
    client.cookies.clear()
    response = await change_status(
        client, login.json()["access_token"], payment, "success"
    )
    assert response.status_code == 403
    wallet = await get_wallet(payment.wallet_id)
    assert wallet
    response = await client.patch(
        "/api/v1/payments/status",
        headers={"X-Api-Key": wallet.adminkey},
        json={
            "wallet_id": wallet.id,
            "checking_id": payment.checking_id,
            "status": "success",
        },
    )
    assert response.status_code in (401, 403)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kind", ["internal", "fiat", "fee", "hold", "offer", "fiat-wallet"]
)
async def test_change_status_external_only(client, superuser_token, from_user, kind):
    payment, _ = await status_payment(from_user)
    if kind in ("internal", "fee", "offer"):
        prefix = {
            "internal": "internal_",
            "fee": "service_fee_",
            "offer": "temp_offer_",
        }[kind]
        payment = await update_payment(payment, new_checking_id=prefix + uuid4().hex)
    elif kind == "fiat":
        payment.fiat_provider = "stripe"
    elif kind == "hold":
        payment.extra["hold_invoice"] = True
    else:
        from lnbits.core.db import db

        await db.execute(
            "UPDATE wallets SET wallet_type = :type WHERE id = :id",
            {"type": WalletType.FIAT.value, "id": payment.wallet_id},
        )
    payment = await update_payment(payment)
    response = await change_status(client, superuser_token, payment, "success")
    assert response.status_code == 400


@pytest.mark.anyio
async def test_change_status_service_fee_is_credited_once(
    client, superuser_token, from_user, settings
):
    fee_wallet = await create_wallet(user_id=from_user.id)
    settings.lnbits_service_fee_wallet = fee_wallet.id
    settings.lnbits_service_fee = 1
    payment, _ = await status_payment(from_user)
    success = await change_status(
        client, superuser_token, payment, "success", fee_msat=50
    )
    assert success.status_code == 200
    assert success.json()["fee"] == -150
    credited_wallet = await get_wallet(fee_wallet.id)
    assert credited_wallet
    assert credited_wallet.balance_msat == 100
    payment = await get_payment(payment.checking_id)
    await change_status(client, superuser_token, payment, "failed")
    payment = await get_payment(payment.checking_id)
    await change_status(client, superuser_token, payment, "success")
    credited_wallet = await get_wallet(fee_wallet.id)
    assert credited_wallet
    assert credited_wallet.balance_msat == 100
