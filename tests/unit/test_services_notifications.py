import asyncio
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from pytest_mock.plugin import MockerFixture
from pywebpush import WebPushException

from lnbits.core.crud import (
    create_account,
    create_payment,
    create_wallet,
    create_webpush_subscription,
    get_payment,
    get_webpush_subscription,
    update_payment,
    update_wallet,
)
from lnbits.core.models import Account, CreatePayment, Payment, PaymentState, Wallet
from lnbits.core.models.notifications import NotificationType
from lnbits.core.models.users import UserExtra, UserNotifications
from lnbits.core.models.wallets import (
    WalletPermission,
    WalletSharePermission,
    WalletShareStatus,
)
from lnbits.core.services.notifications import (
    dispatch_webhook,
    enqueue_admin_notification,
    enqueue_user_notification,
    process_next_notification,
    send_admin_notification,
    send_chat_payment_notification,
    send_email,
    send_email_notification,
    send_nostr_notification,
    send_nostr_notifications,
    send_notification,
    send_payment_notification,
    send_payment_push_notification,
    send_push_notification,
    send_telegram_message,
    send_telegram_notification,
    send_user_notification,
    send_ws_payment_notification,
)
from lnbits.settings import Settings


class MockHTTPClient:
    def __init__(self, post_response=None, post_exception=None):
        self.post_response = post_response
        self.post_exception = post_exception
        self.posts: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if self.post_exception:
            raise self.post_exception
        return self.post_response


@pytest.mark.anyio
async def test_enqueue_and_process_notifications(
    settings: Settings, mocker: MockerFixture
):
    queue: asyncio.Queue = asyncio.Queue()
    admin_mock = mocker.patch(
        "lnbits.core.services.notifications.send_admin_notification",
        mocker.AsyncMock(),
    )
    user_mock = mocker.patch(
        "lnbits.core.services.notifications.send_user_notification",
        mocker.AsyncMock(),
    )
    mocker.patch("lnbits.core.services.notifications.notifications_queue", queue)
    mocker.patch(
        "lnbits.core.services.notifications._is_message_type_enabled",
        return_value=True,
    )

    enqueue_admin_notification(NotificationType.settings_update, {"username": "alice"})
    await process_next_notification()

    assert admin_mock.await_count == 1
    assert admin_mock.await_args is not None
    assert admin_mock.await_args.args[0].startswith(f"[{settings.lnbits_site_title}]")
    assert "alice" in admin_mock.await_args.args[0]
    assert admin_mock.await_args.args[1] == NotificationType.settings_update.value

    user_notifications = UserNotifications(email_address="alice@example.com")
    enqueue_user_notification(
        NotificationType.text_message,
        {"message": "hello"},
        user_notifications,
    )
    await process_next_notification()

    assert user_mock.await_count == 1
    assert user_mock.await_args is not None
    assert user_mock.await_args.args[0] == user_notifications
    assert "hello" in user_mock.await_args.args[1]
    assert user_mock.await_args.args[2] == NotificationType.text_message.value


@pytest.mark.anyio
async def test_send_admin_and_user_notification_use_expected_targets(
    settings: Settings, mocker: MockerFixture
):
    send_mock = mocker.patch(
        "lnbits.core.services.notifications.send_notification",
        mocker.AsyncMock(),
    )
    original_chat_id = settings.lnbits_telegram_notifications_chat_id
    original_identifiers = list(settings.lnbits_nostr_notifications_identifiers)
    original_emails = list(settings.lnbits_email_notifications_to_emails)
    try:
        settings.lnbits_telegram_notifications_chat_id = "chat-id"
        settings.lnbits_nostr_notifications_identifiers = ["alice@example.com"]
        settings.lnbits_email_notifications_to_emails = ["admin@example.com"]

        await send_admin_notification("hello", "settings_update")
        await send_user_notification(
            UserNotifications(
                telegram_chat_id="user-chat",
                nostr_identifier="bob@example.com",
                email_address="bob@example.com",
            ),
            "hello user",
            "text_message",
        )
    finally:
        settings.lnbits_telegram_notifications_chat_id = original_chat_id
        settings.lnbits_nostr_notifications_identifiers = original_identifiers
        settings.lnbits_email_notifications_to_emails = original_emails

    assert send_mock.await_args_list[0].args == (
        "chat-id",
        ["alice@example.com"],
        ["admin@example.com"],
        "hello",
        "settings_update",
    )
    assert send_mock.await_args_list[1].args == (
        "user-chat",
        ["bob@example.com"],
        ["bob@example.com"],
        "hello user",
        "text_message",
    )


@pytest.mark.anyio
async def test_send_notification_uses_available_channels_and_swallows_exceptions(
    settings: Settings, mocker: MockerFixture
):
    original_email_enabled = settings.lnbits_email_notifications_enabled
    try:
        settings.lnbits_email_notifications_enabled = True
        mocker.patch.object(
            type(settings),
            "is_telegram_notifications_configured",
            return_value=True,
        )
        mocker.patch.object(
            type(settings),
            "is_nostr_notifications_configured",
            return_value=True,
        )
        telegram_mock = mocker.patch(
            "lnbits.core.services.notifications.send_telegram_notification",
            mocker.AsyncMock(side_effect=Exception("telegram boom")),
        )
        nostr_mock = mocker.patch(
            "lnbits.core.services.notifications.send_nostr_notifications",
            mocker.AsyncMock(return_value=["alice@example.com"]),
        )
        email_mock = mocker.patch(
            "lnbits.core.services.notifications.send_email_notification",
            mocker.AsyncMock(side_effect=Exception("email boom")),
        )

        await send_notification(
            "chat-id",
            ["alice@example.com"],
            ["alice@example.com"],
            "hello",
            "text_message",
        )
    finally:
        settings.lnbits_email_notifications_enabled = original_email_enabled

    telegram_mock.assert_awaited_once()
    nostr_mock.assert_awaited_once()
    email_mock.assert_awaited_once()


@pytest.mark.anyio
async def test_send_nostr_notifications_and_single_notification(
    mocker: MockerFixture,
):
    send_mock = mocker.patch(
        "lnbits.core.services.notifications.send_nostr_notification",
        mocker.AsyncMock(side_effect=[None, Exception("boom"), None]),
    )

    result = await send_nostr_notifications(["ok-1", "bad", "ok-2"], "hello")

    assert result == ["ok-1", "ok-2"]
    assert send_mock.await_count == 3

    fetch_mock = mocker.patch(
        "lnbits.core.services.notifications.fetch_nip5_details",
        mocker.AsyncMock(return_value=("pubkey", ["wss://relay"])),
    )
    normalize_mock = mocker.patch(
        "lnbits.core.services.notifications.normalize_private_key",
        return_value="server-private-key",
    )
    dm_mock = mocker.patch(
        "lnbits.core.services.notifications.send_nostr_dm",
        mocker.AsyncMock(),
    )

    await send_nostr_notification("alice@example.com", "hello")

    fetch_mock.assert_awaited_once_with("alice@example.com")
    normalize_mock.assert_called_once()
    dm_mock.assert_awaited_once_with(
        "server-private-key",
        "pubkey",
        "hello",
        ["wss://relay"],
    )


@pytest.mark.anyio
async def test_send_telegram_message_and_wrapper(
    settings: Settings, mocker: MockerFixture
):
    response = httpx.Response(
        200,
        request=httpx.Request("POST", "https://api.telegram.org"),
        json={"ok": True},
    )
    client = MockHTTPClient(post_response=response)
    mocker.patch(
        "lnbits.core.services.notifications.httpx.AsyncClient",
        return_value=client,
    )

    result = await send_telegram_message("token", "chat-id", "hello")

    assert result == {"ok": True}
    assert client.posts[0][0].endswith("/bottoken/sendMessage")

    original_token = settings.lnbits_telegram_notifications_access_token
    try:
        settings.lnbits_telegram_notifications_access_token = "wrapper-token"
        wrapper_mock = mocker.patch(
            "lnbits.core.services.notifications.send_telegram_message",
            mocker.AsyncMock(return_value={"ok": True}),
        )

        await send_telegram_notification("chat-id", "hello")
    finally:
        settings.lnbits_telegram_notifications_access_token = original_token

    wrapper_mock.assert_awaited_once_with("wrapper-token", "chat-id", "hello")


@pytest.mark.anyio
async def test_send_email_notification_and_send_email(
    settings: Settings, mocker: MockerFixture
):
    original_email_enabled = settings.lnbits_email_notifications_enabled
    try:
        settings.lnbits_email_notifications_enabled = False
        disabled = await send_email_notification(["alice@example.com"], "hello")
        assert disabled["status"] == "error"

        settings.lnbits_email_notifications_enabled = True
        send_email_mock = mocker.patch(
            "lnbits.core.services.notifications.send_email",
            mocker.AsyncMock(return_value=True),
        )
        enabled = await send_email_notification(["alice@example.com"], "hello")
        assert enabled == {"status": "ok"}
        send_email_mock.assert_awaited_once()
    finally:
        settings.lnbits_email_notifications_enabled = original_email_enabled

    smtp_server = MagicMock()
    smtp_context = MagicMock()
    smtp_context.__enter__.return_value = smtp_server
    smtp_context.__exit__.return_value = None
    mocker.patch(
        "lnbits.core.services.notifications.smtplib.SMTP",
        return_value=smtp_context,
    )

    assert (
        await send_email(
            "smtp.example.com",
            587,
            "",
            "password",
            "from@example.com",
            ["to@example.com"],
            "Subject",
            "Body",
        )
        is True
    )
    smtp_server.starttls.assert_called_once()
    smtp_server.login.assert_called_once_with("from@example.com", "password")
    smtp_server.sendmail.assert_called_once()

    with pytest.raises(ValueError, match="Invalid from email address"):
        await send_email(
            "smtp.example.com",
            587,
            "user",
            "password",
            "bad-email",
            ["to@example.com"],
            "Subject",
            "Body",
        )

    with pytest.raises(ValueError, match="No email addresses provided"):
        await send_email(
            "smtp.example.com",
            587,
            "user",
            "password",
            "from@example.com",
            [],
            "Subject",
            "Body",
        )


@pytest.mark.anyio
async def test_dispatch_webhook_marks_missing_invalid_and_failed_requests(
    mocker: MockerFixture,
):
    wallet = await _create_wallet()

    payment = await _create_payment(wallet, webhook=None)
    await dispatch_webhook(payment)
    assert (await get_payment(payment.checking_id)).webhook_status == "-1"

    invalid_payment = await _create_payment(wallet, webhook="https://invalid.example")
    assert invalid_payment.webhook is not None
    invalid_client = MockHTTPClient(
        post_response=httpx.Response(
            200,
            request=httpx.Request("POST", invalid_payment.webhook),
            json={"ok": True},
        )
    )
    mocker.patch(
        "lnbits.core.services.notifications.check_callback_url",
        side_effect=ValueError("blocked"),
    )
    mocker.patch(
        "lnbits.core.services.notifications.httpx.AsyncClient",
        return_value=invalid_client,
    )

    await dispatch_webhook(invalid_payment)
    assert (await get_payment(invalid_payment.checking_id)).webhook_status in {
        "-1",
        "200",
    }

    error_payment = await _create_payment(wallet, webhook="https://error.example")
    assert error_payment.webhook is not None
    mocker.patch(
        "lnbits.core.services.notifications.check_callback_url",
        return_value=None,
    )
    mocker.patch(
        "lnbits.core.services.notifications.httpx.AsyncClient",
        return_value=MockHTTPClient(
            post_response=httpx.Response(
                500,
                request=httpx.Request("POST", error_payment.webhook),
            )
        ),
    )

    await dispatch_webhook(error_payment)
    assert (await get_payment(error_payment.checking_id)).webhook_status == "500"

    request_payment = await _create_payment(wallet, webhook="https://request.example")
    assert request_payment.webhook is not None
    mocker.patch(
        "lnbits.core.services.notifications.httpx.AsyncClient",
        return_value=MockHTTPClient(
            post_exception=httpx.RequestError(
                "boom",
                request=httpx.Request("POST", request_payment.webhook),
            )
        ),
    )

    await dispatch_webhook(request_payment)
    assert (await get_payment(request_payment.checking_id)).webhook_status == "-1"


@pytest.mark.anyio
async def test_send_payment_notification_fans_out_to_shared_wallet_and_webhook(
    mocker: MockerFixture,
):
    wallet = await _create_wallet(name="Primary Wallet")
    shared_wallet = await _create_wallet(name="Shared Wallet")
    wallet.extra.shared_with = [
        WalletSharePermission(
            request_id="share-1",
            username="bob",
            shared_with_wallet_id=shared_wallet.id,
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.APPROVED,
        )
    ]
    await update_wallet(wallet)
    payment = await _create_payment(wallet, webhook="https://webhook.example")
    ws_mock = mocker.patch(
        "lnbits.core.services.notifications.send_ws_payment_notification",
        mocker.AsyncMock(),
    )
    chat_mock = mocker.patch(
        "lnbits.core.services.notifications.send_chat_payment_notification",
        mocker.AsyncMock(),
    )
    push_mock = mocker.patch(
        "lnbits.core.services.notifications.send_payment_push_notification",
        mocker.AsyncMock(),
    )
    dispatch_mock = mocker.patch(
        "lnbits.core.services.notifications.dispatch_webhook",
        mocker.AsyncMock(),
    )

    await send_payment_notification(wallet, payment)

    assert [call.args[0].id for call in ws_mock.await_args_list] == [
        wallet.id,
        shared_wallet.id,
    ]
    chat_mock.assert_awaited_once_with(wallet, payment)
    push_mock.assert_awaited_once_with(wallet, payment)
    dispatch_mock.assert_awaited_once_with(payment)


@pytest.mark.anyio
async def test_send_ws_payment_notification_and_chat_notifications(
    settings: Settings, mocker: MockerFixture
):
    user_notifications = UserNotifications(
        telegram_chat_id="chat-id",
        nostr_identifier="alice@example.com",
        email_address="alice@example.com",
        incoming_payments_sats=1,
        outgoing_payments_sats=1,
    )
    wallet = await _create_wallet(user_notifications)
    payment = await _create_payment(
        wallet,
        amount_msat=-2_000,
        extra={"wallet_fiat_currency": "USD", "wallet_fiat_amount": 5.25},
    )
    websocket_mock = mocker.patch(
        "lnbits.core.services.notifications.websocket_manager.send",
        mocker.AsyncMock(),
    )

    await send_ws_payment_notification(wallet, payment)

    assert [call.args[0] for call in websocket_mock.await_args_list] == [
        wallet.inkey,
        wallet.adminkey,
        payment.payment_hash,
    ]

    original_outgoing = settings.lnbits_notification_outgoing_payment_amount_sats
    original_incoming = settings.lnbits_notification_incoming_payment_amount_sats
    try:
        settings.lnbits_notification_outgoing_payment_amount_sats = 1
        settings.lnbits_notification_incoming_payment_amount_sats = 1
        admin_mock = mocker.patch(
            "lnbits.core.services.notifications.enqueue_admin_notification"
        )
        user_mock = mocker.patch(
            "lnbits.core.services.notifications.enqueue_user_notification"
        )

        await send_chat_payment_notification(wallet, payment)
    finally:
        settings.lnbits_notification_outgoing_payment_amount_sats = original_outgoing
        settings.lnbits_notification_incoming_payment_amount_sats = original_incoming

    assert admin_mock.call_args.args[0] == NotificationType.outgoing_payment
    assert "`5.25`*USD* / " in admin_mock.call_args.args[1]["fiat_value_fmt"]
    assert user_mock.call_args.args[0] == NotificationType.outgoing_payment


@pytest.mark.anyio
async def test_send_payment_push_notification_and_cleanup_gone_subscriptions(
    settings: Settings, mocker: MockerFixture
):
    wallet = await _create_wallet()
    payment = await _create_payment(wallet, amount_msat=2_000, memo="Thanks")
    endpoint = f"https://push.example/{uuid4().hex}"
    subscription = await create_webpush_subscription(
        endpoint,
        wallet.user,
        '{"endpoint":"https://push.example"}',
        "push.example",
    )
    send_push_mock = mocker.patch(
        "lnbits.core.services.notifications.send_push_notification",
        mocker.AsyncMock(),
    )

    await send_payment_push_notification(wallet, payment)

    assert send_push_mock.await_args is not None
    assert send_push_mock.await_args.args[0].endpoint == subscription.endpoint
    assert send_push_mock.await_args.args[1] == f"LNbits: {wallet.name}"
    assert "received 2 sats" in send_push_mock.await_args.args[2]
    assert send_push_mock.await_args.args[3] == (
        f"https://{subscription.host}/wallet?usr={wallet.user}&wal={wallet.id}"
    )

    original_privkey = settings.lnbits_webpush_privkey
    try:
        settings.lnbits_webpush_privkey = ""
        exc = WebPushException("gone")
        exc.response = SimpleNamespace(status_code=HTTPStatus.GONE, text="gone")
        mocker.patch(
            "lnbits.core.services.notifications.webpush",
            side_effect=exc,
        )

        await send_push_notification(subscription, "Title", "Body")
    finally:
        settings.lnbits_webpush_privkey = original_privkey

    assert await get_webpush_subscription(subscription.endpoint, wallet.user) is None


async def _create_wallet(
    notifications: UserNotifications | None = None,
    *,
    name: str | None = None,
) -> Wallet:
    account = Account(
        id=uuid4().hex,
        username=f"user_{uuid4().hex[:8]}",
        extra=UserExtra(notifications=notifications or UserNotifications()),
    )
    await create_account(account)
    return await create_wallet(
        user_id=account.id,
        wallet_name=name or f"wallet_{account.id[:8]}",
    )


async def _create_payment(
    wallet: Wallet,
    *,
    amount_msat: int = 2_000,
    status: PaymentState = PaymentState.SUCCESS,
    webhook: str | None = None,
    webhook_status: str | None = None,
    memo: str | None = "memo",
    extra: dict | None = None,
) -> Payment:
    checking_id = f"checking_{uuid4().hex[:8]}"
    payment = await create_payment(
        checking_id=checking_id,
        data=CreatePayment(
            wallet_id=wallet.id,
            payment_hash=uuid4().hex,
            bolt11=f"bolt11-{checking_id}",
            amount_msat=amount_msat,
            memo=memo or "",
            webhook=webhook,
            extra=extra or {},
        ),
        status=status,
    )
    if webhook_status is not None:
        payment.webhook_status = webhook_status
        await update_payment(payment)
    return await get_payment(checking_id)
