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
@pytest.mark.parametrize("send_notifications", [True, False])
@pytest.mark.parametrize("amount", [-10_000, 10_000])
@pytest.mark.parametrize(
    "old,new",
    [(old, new) for old in PaymentState for new in PaymentState if old != new],
)
async def test_change_status_notifies_only_on_success(
    client, superuser_token, from_user, mocker, amount, old, new, send_notifications
):
    payment, _ = await status_payment(from_user, old, amount)
    notify = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background"
    )
    webhook = mocker.patch("lnbits.core.services.notifications.dispatch_webhook")
    backend = mocker.patch("lnbits.core.services.payments.get_funding_source")
    incoming = mocker.patch.object(task_manager.invoice_queue, "put_nowait")
    internal = mocker.patch.object(task_manager.internal_invoice_queue, "put_nowait")
    response = await change_status(
        client,
        superuser_token,
        payment,
        new,
        send_payment_notifications=send_notifications,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == new
    assert result["labels"] == ["existing", "status-changed"]
    assert result["fee"] == (0 if new == PaymentState.SUCCESS else payment.fee)
    assert result["extra"] == payment.extra
    assert result["amount"] == payment.amount
    assert result["webhook"] == payment.webhook
    if new == PaymentState.SUCCESS and send_notifications:
        notify.assert_called_once()
        wallet, notified_payment = notify.call_args.args
        stored_wallet = await get_wallet(payment.wallet_id)
        assert stored_wallet
        assert wallet.id == payment.wallet_id
        assert wallet.balance_msat == stored_wallet.balance_msat
        assert (
            notified_payment.model_dump()
            == (await get_payment(payment.checking_id)).model_dump()
        )
    else:
        notify.assert_not_called()
    for side_effect in [webhook, backend, incoming, internal]:
        side_effect.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("amount", [-10_000, 10_000])
@pytest.mark.parametrize("status", [PaymentState.PENDING, PaymentState.FAILED])
async def test_change_status_success_can_skip_notifications(
    client, superuser_token, from_user, notification_tasks, amount, status
):
    payment, preimage = await status_payment(from_user, status, amount)
    response = await change_status(
        client,
        superuser_token,
        payment,
        "success",
        fee_msat=321,
        preimage=preimage,
        send_payment_notifications=False,
    )
    assert response.status_code == 200
    assert not notification_tasks
    stored_payment = await get_payment(payment.checking_id)
    assert stored_payment.success
    assert stored_payment.fee == -321
    assert stored_payment.preimage == preimage
    assert stored_payment.labels == ["existing", "status-changed"]
    assert stored_payment.webhook_status is None


@pytest.mark.anyio
@pytest.mark.parametrize("amount", [-10_000, 10_000])
@pytest.mark.parametrize("status", [PaymentState.PENDING, PaymentState.FAILED])
@pytest.mark.parametrize("webhook_status", [None, "200", "-1"])
async def test_change_status_success_dispatches_notifications_and_webhook(
    client,
    superuser_token,
    from_user,
    mocker,
    notification_tasks,
    amount,
    status,
    webhook_status,
):
    payment, preimage = await status_payment(from_user, status, amount)
    payment.webhook_status = webhook_status
    payment = await update_payment(payment)
    ws = mocker.patch("lnbits.core.services.notifications.send_ws_payment_notification")
    chat = mocker.patch(
        "lnbits.core.services.notifications.send_chat_payment_notification"
    )
    push = mocker.patch(
        "lnbits.core.services.notifications.send_payment_push_notification"
    )
    webhook = mocker.patch(
        "lnbits.core.services.notifications._post_webhook", return_value=200
    )

    response = await change_status(
        client, superuser_token, payment, "success", fee_msat=321, preimage=preimage
    )
    assert response.status_code == 200
    assert len(notification_tasks) == 1
    await notification_tasks[0]

    notified_wallet, notified_payment = ws.await_args.args
    stored_wallet = await get_wallet(payment.wallet_id)
    assert stored_wallet
    assert notified_wallet.id == payment.wallet_id
    assert notified_wallet.balance_msat == stored_wallet.balance_msat
    assert notified_payment.success
    assert notified_payment.preimage == preimage
    assert notified_payment.fee == -321
    assert notified_payment.labels == ["existing", "status-changed"]
    ws.assert_awaited_once()
    chat.assert_awaited_once_with(notified_wallet, notified_payment)
    push.assert_awaited_once_with(notified_wallet, notified_payment)
    if webhook_status is None:
        webhook.assert_awaited_once_with(notified_payment)
        assert (await get_payment(payment.checking_id)).webhook_status == "200"
    else:
        webhook.assert_not_awaited()
        assert (await get_payment(payment.checking_id)).webhook_status == webhook_status

    repeated = await change_status(client, superuser_token, payment, "success")
    assert repeated.status_code == 200
    assert len(notification_tasks) == 1


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
    client, superuser_token, from_user, notification_tasks
):
    payment, _ = await status_payment(from_user)
    noop = await change_status(client, superuser_token, payment, "pending")
    assert noop.status_code == 200
    assert noop.json()["labels"] == ["existing"]
    assert (await get_payment(payment.checking_id)).updated_at == payment.updated_at
    assert not notification_tasks
    await change_status(client, superuser_token, payment, "success")
    assert len(notification_tasks) == 1
    changed = await change_status(client, superuser_token, payment, "failed")
    assert changed.status_code == 200
    assert changed.json()["status"] == "failed"
    assert len(notification_tasks) == 1


@pytest.mark.anyio
async def test_change_status_uses_exact_wallet_and_checking_id(
    client, superuser_token, from_user
):
    from lnbits.core.db import db

    payment, _ = await status_payment(from_user)
    other_wallet = await create_wallet(user_id=from_user.id)
    other_payment = payment.model_copy(update={"wallet_id": other_wallet.id})
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


@pytest.fixture(autouse=True)
def notification_tasks(mocker):
    tasks = []
    # Background admin alerts must not enter the captured payment task list.
    mocker.patch("lnbits.core.services.notifications.send_notification_in_background")
    mocker.patch(
        "lnbits.core.services.notifications.create_task", side_effect=tasks.append
    )
    yield tasks
    for task in tasks:
        task.close()
