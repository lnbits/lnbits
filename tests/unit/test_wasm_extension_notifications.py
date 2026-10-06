import asyncio
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture
from wasmtime import Config, Engine, Store, component, wat2wasm

from lnbits.core.models.extensions import ExtensionPermission, WasmInvocation
from lnbits.core.models.users import UserNotifications
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import SendUserNotificationRequest
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.core.wasm_ext.wasm.host import add_extension_host_imports
from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export
from lnbits.helpers import sha256s
from tests.helpers import make_installable_extension

METHOD = "notifications.send_user_notification"
MESSAGE = "A payment was received for your form."
REQUEST = {"type": "email", "message": MESSAGE}
DESTINATIONS = {
    "email": (None, [], ["owner@example.com"]),
    "nostr": (None, ["owner@example.com"], []),
    "telegram": ("123456", [], []),
}


@pytest.fixture(params=["email", "nostr", "telegram"])
def notification_type(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def notification_user(mocker: MockerFixture):
    user = SimpleNamespace(
        id="recipient-user",
        extra=SimpleNamespace(
            notifications=UserNotifications(
                email_address="owner@example.com",
                nostr_identifier="owner@example.com",
                telegram_chat_id="123456",
            )
        ),
    )
    mocker.patch("lnbits.core.crud.users.get_account", AsyncMock(return_value=user))
    return user


@pytest.fixture
def notification_sender(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "lnbits.core.services.notifications.send_notification_in_background",
        AsyncMock(),
    )


@pytest.fixture
def event_invocation(mocker: MockerFixture) -> WasmInvocation:
    invocation = WasmInvocation(
        id="invocation-1",
        extension_id="forms",
        export_name="on_invoice_paid",
        trigger_type="event",
        user_id=sha256s("source-user"),
        wallet_id="event-wallet",
    )
    mocker.patch(
        "lnbits.core.crud.extensions.get_wasm_invocation",
        AsyncMock(return_value=invocation),
    )
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet",
        AsyncMock(return_value=SimpleNamespace(user="recipient-user")),
    )
    return invocation


def event_api(*, user_id: str | None = "recipient-user", **kwargs) -> ExtensionHostAPI:
    return ExtensionHostAPI(
        "forms",
        [METHOD],
        context="event",
        user_id=user_id,
        **kwargs,
    )


@pytest.mark.anyio
async def test_notification_prefers_host_user_without_loading_invocation(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    mocker: MockerFixture,
):
    get_invocation = mocker.patch(
        "lnbits.core.crud.extensions.get_wasm_invocation", AsyncMock()
    )
    get_wallet = mocker.patch("lnbits.core.crud.wallets.get_wallet", AsyncMock())
    get_account = mocker.patch(
        "lnbits.core.crud.users.get_account", AsyncMock(return_value=notification_user)
    )
    api = ExtensionHostAPI(
        "forms", [METHOD], user_id="recipient-user", invocation_id="invocation-1"
    )

    await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    get_account.assert_awaited_once_with("recipient-user")
    get_invocation.assert_not_called()
    get_wallet.assert_not_called()
    notification_sender.assert_awaited_once()


@pytest.mark.anyio
async def test_notification_resolves_wallet_owner_without_changing_host_identity(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    event_invocation: WasmInvocation,
    mocker: MockerFixture,
):
    get_invocation = mocker.patch(
        "lnbits.core.crud.extensions.get_wasm_invocation",
        AsyncMock(return_value=event_invocation),
    )
    get_wallet = mocker.patch(
        "lnbits.core.crud.wallets.get_wallet",
        AsyncMock(return_value=SimpleNamespace(user="recipient-user")),
    )
    get_account = mocker.patch(
        "lnbits.core.crud.users.get_account", AsyncMock(return_value=notification_user)
    )
    api = event_api(
        user_id=None,
        invocation_id=event_invocation.id,
        owner_id=event_invocation.user_id,
    )

    assert await ExtensionAPIHost(api).invoke(METHOD, REQUEST) == {"queued": True}

    get_invocation.assert_awaited_once_with("invocation-1")
    get_wallet.assert_awaited_once_with("event-wallet")
    get_account.assert_awaited_once_with("recipient-user")
    notification_sender.assert_awaited_once()
    assert api.user_id is None
    assert api.owner_id == sha256s("source-user")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields",
    [
        None,
        {"wallet_id": None},
        {"wallet_id": ""},
        {"extension_id": "another-extension"},
    ],
)
async def test_notification_rejects_missing_or_mismatched_event_metadata(
    notification_sender: AsyncMock,
    event_invocation: WasmInvocation,
    mocker: MockerFixture,
    fields: dict | None,
):
    invocation = event_invocation.copy(update=fields) if fields is not None else None
    mocker.patch(
        "lnbits.core.crud.extensions.get_wasm_invocation",
        AsyncMock(return_value=invocation),
    )
    get_wallet = mocker.patch("lnbits.core.crud.wallets.get_wallet", AsyncMock())
    get_account = mocker.patch("lnbits.core.crud.users.get_account", AsyncMock())
    api = event_api(
        user_id=None,
        invocation_id=event_invocation.id,
        owner_id=event_invocation.user_id,
    )

    with pytest.raises(PermissionError, match="no notification recipient"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    get_wallet.assert_not_called()
    get_account.assert_not_called()
    notification_sender.assert_not_called()


@pytest.mark.anyio
async def test_notification_rejects_missing_event_wallet(
    notification_sender: AsyncMock,
    event_invocation: WasmInvocation,
    mocker: MockerFixture,
):
    get_wallet = mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", AsyncMock(return_value=None)
    )
    get_account = mocker.patch("lnbits.core.crud.users.get_account", AsyncMock())
    api = event_api(user_id=None, invocation_id=event_invocation.id)

    with pytest.raises(PermissionError, match="no notification recipient"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    get_wallet.assert_awaited_once_with("event-wallet")
    get_account.assert_not_called()
    notification_sender.assert_not_called()


@pytest.mark.anyio
async def test_user_notification_uses_only_selected_saved_user_destination(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    mocker: MockerFixture,
    notification_type: str,
):
    admin = mocker.patch(
        "lnbits.core.services.notifications.send_admin_notification", AsyncMock()
    )

    preferences_before = notification_user.extra.notifications.copy(deep=True)
    api = ExtensionHostAPI("forms", [METHOD], user_id="recipient-user")
    result = await ExtensionAPIHost(api).invoke(
        METHOD, {**REQUEST, "type": notification_type}
    )

    assert notification_user.extra.notifications == preferences_before

    assert result == {"queued": True}
    notification_sender.assert_awaited_once_with(
        *DESTINATIONS[notification_type], MESSAGE, None
    )
    admin.assert_not_called()


@pytest.mark.anyio
async def test_missing_selected_destination_does_not_fall_back_to_other_channels(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    notification_type: str,
):
    field = {
        "email": "email_address",
        "nostr": "nostr_identifier",
        "telegram": "telegram_chat_id",
    }[notification_type]
    setattr(notification_user.extra.notifications, field, None)

    await ExtensionAPIHost(event_api()).invoke(
        METHOD, {**REQUEST, "type": notification_type}
    )

    notification_sender.assert_awaited_once_with(None, [], [], MESSAGE, None)


@pytest.mark.anyio
async def test_unauthenticated_user_cannot_send_notifications(
    notification_sender: AsyncMock,
    event_invocation: WasmInvocation,
    mocker: MockerFixture,
):
    get_account = mocker.patch("lnbits.core.crud.users.get_account", AsyncMock())
    api = ExtensionHostAPI(
        "forms", [METHOD], invocation_id=event_invocation.id, owner_id="owner-1"
    )

    with pytest.raises(PermissionError, match="requires authentication"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    get_account.assert_not_called()
    notification_sender.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("context", ["user", "event"])
async def test_notification_requires_install_permission(
    notification_sender: AsyncMock,
    context: str,
):
    api = ExtensionHostAPI(
        "forms",
        [],
        context=context,
        user_id="recipient-user" if context == "user" else None,
    )

    with pytest.raises(PermissionError, match="missing permission"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    notification_sender.assert_not_called()


@pytest.mark.anyio
async def test_notification_without_user_or_invocation_rejects_owner_hash(
    notification_sender: AsyncMock, mocker: MockerFixture
):
    get_account = mocker.patch("lnbits.core.crud.users.get_account", AsyncMock())
    api = ExtensionHostAPI(
        "forms",
        [METHOD],
        context="event",
        owner_id=sha256s("source-user"),
    )

    with pytest.raises(PermissionError, match="no notification recipient"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    get_account.assert_not_called()
    notification_sender.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("user_id", ["recipient-user", None])
async def test_notification_rejects_missing_or_inactive_user(
    notification_sender: AsyncMock,
    event_invocation: WasmInvocation,
    mocker: MockerFixture,
    user_id: str | None,
):
    get_account = mocker.patch(
        "lnbits.core.crud.users.get_account", AsyncMock(return_value=None)
    )
    api = event_api(user_id=user_id, invocation_id=event_invocation.id)

    with pytest.raises(ValueError, match="recipient is unavailable"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    get_account.assert_awaited_once_with("recipient-user")
    notification_sender.assert_not_called()


@pytest.mark.parametrize("message", ["", " ", "\n\t", "x" * 4097])
def test_notification_validates_message(message: str):
    with pytest.raises(ValidationError):
        SendUserNotificationRequest(type="email", message=message)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields",
    [{}, {"type": None}, {"type": "sms"}, {"type": "Email"}, {"type": []}],
)
async def test_notification_requires_supported_type(
    notification_sender: AsyncMock, fields: dict
):
    with pytest.raises(ValidationError):
        await ExtensionAPIHost(event_api()).invoke(
            METHOD, {"message": MESSAGE, **fields}
        )

    notification_sender.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields",
    [
        {"userId": "another-user"},
        {"notificationUserId": "another-user"},
        {"ownerId": "another-owner"},
        {"invocationId": "another-invocation"},
        {"walletId": "another-wallet"},
        {"to": ["another@example.com"]},
        {"chatId": "123"},
        {"subject": "Custom subject"},
        {"triggerType": "event"},
        {"context": "event"},
    ],
)
async def test_extension_cannot_supply_recipients_or_context(
    notification_sender: AsyncMock, fields: dict
):
    with pytest.raises(ValidationError):
        await ExtensionAPIHost(event_api()).invoke(METHOD, {**REQUEST, **fields})

    notification_sender.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("channel", ["email", "nostr", "telegram"])
async def test_raw_notification_methods_are_not_exposed(channel: str):
    with pytest.raises(KeyError, match="Unknown extension host function"):
        await ExtensionAPIHost(event_api()).invoke(f"notifications.send_{channel}")


def test_notification_permission_and_sdk_are_available():
    permission = ExtensionPermission(id=METHOD)
    config = {
        "id": "forms",
        "name": "Forms",
        "version": "0.1.0",
        "short_description": "Forms",
        "extension_type": "wasm",
        "wasm": {"module": "extension.wasm"},
        "permissions": [permission.dict()],
    }
    extension = make_installable_extension("forms")

    with pytest.raises(ValueError, match="requires permission approval"):
        validate_wasm_extension_permissions(extension, None, config)
    assert validate_wasm_extension_permissions(extension, [permission], config) == [
        permission
    ]

    codegen = run_path(
        str(
            Path(__file__).resolve().parents[2]
            / "tools/codegen/extension_sdk_typescript.py"
        )
    )
    sdk = codegen["generate_typescript_sdk"](method_ids=[METHOD])
    assert "message: string" in sdk
    assert 'type: "email" | "nostr" | "telegram"' in sdk
    assert "sendUserNotification(input: SendUserNotificationRequest)" in sdk
    assert "Promise<SendUserNotificationResponse>" in sdk
    assert "return host.host.notificationsSendUserNotification(input)" in sdk
    assert "userId" not in sdk
    assert "chatId" not in sdk


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("context", "user_id", "trigger_type"),
    [
        ("user", "recipient-user", "http"),
        ("user", "recipient-user", "unknown"),
        ("event", None, "event"),
        ("event", None, "http"),
        ("event", None, "unknown"),
    ],
)
async def test_invocation_notifies_current_user_or_wallet_owner_regardless_of_trigger(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    event_invocation: WasmInvocation,
    mocker: MockerFixture,
    context: str,
    user_id: str | None,
    trigger_type: str,
):
    event_invocation.trigger_type = trigger_type
    expected_owner_id = sha256s(user_id) if user_id else "source-owner"
    wallet_id = None if user_id else event_invocation.wallet_id
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._get_registered_extension",
        return_value=SimpleNamespace(id="forms"),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._active_installed_extension",
        AsyncMock(return_value=SimpleNamespace(permissions=[METHOD])),
    )
    mocker.patch(
        "lnbits.core.services.extensions.resolve_wasm_runtime_limits",
        return_value={
            "wasm_runtime_max_request_bytes": 4096,
            "wasm_runtime_max_execution_ms": 1000,
        },
    )
    start = mocker.patch(
        "lnbits.core.services.extensions.start_wasm_invocation",
        AsyncMock(return_value=SimpleNamespace(id="invocation-1")),
    )
    mocker.patch("lnbits.core.services.extensions.finish_wasm_invocation", AsyncMock())
    mocker.patch("lnbits.core.services.extensions.record_wasm_invocation_host_call")

    def invoke_notification(
        _extension, _export, payload, api, loop, _invocation, _limits
    ):
        assert api.invocation_id == event_invocation.id
        assert api.user_id == user_id
        assert api.owner_id == expected_owner_id
        result = asyncio.run_coroutine_threadsafe(
            ExtensionAPIHost(api).invoke(
                METHOD, {"message": payload["message"], "type": payload["type"]}
            ),
            loop,
        ).result()
        assert api.user_id == user_id
        assert api.owner_id == expected_owner_id
        return result

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=invoke_notification,
    )
    call = invoke_wasm_extension_export(
        "forms",
        "on_invoice_paid",
        {
            **REQUEST,
            "triggerType": "event",
            "userId": "another-user",
            "walletId": "another-wallet",
            "invocationId": "another-invocation",
        },
        context=context,
        user=notification_user if user_id else None,
        owner_id="source-owner",
        trigger_type=trigger_type,
        wallet_id=wallet_id,
    )

    assert await call == {"queued": True}
    notification_sender.assert_awaited_once_with(
        None, [], ["owner@example.com"], MESSAGE, None
    )

    assert start.await_args is not None
    assert start.await_args.kwargs["wallet_id"] == wallet_id
    assert start.await_args.kwargs["trigger_type"] == trigger_type


@pytest.mark.anyio
@pytest.mark.parametrize("recipient_source", ["user", "wallet"])
async def test_notification_component_model_import(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    notification_type: str,
    event_invocation: WasmInvocation,
    recipient_source: str,
):
    loop = asyncio.get_running_loop()
    api = (
        ExtensionHostAPI("forms", [METHOD], user_id="recipient-user")
        if recipient_source == "user"
        else event_api(user_id=None, invocation_id=event_invocation.id)
    )

    def call_import():
        config = Config()
        config.wasm_component_model = True
        engine = Engine(config)
        store = Store(engine)
        linker = component.Linker(engine)
        add_extension_host_imports(linker, ExtensionAPIHost(api), loop)
        compiled = component.Component(
            engine,
            wat2wasm("""(component
            (import "lnbits:extension/host" (instance $host
                (type $request-def (record
                    (field "type" string) (field "message" string)))
                (export "send-user-notification-request"
                    (type $request (eq $request-def)))
                (type $response-def (record (field "queued" bool)))
                (export "send-user-notification-response"
                    (type $response (eq $response-def)))
                (export "notifications-send-user-notification" (func
                    (param "request" $request) (result $response)))))
            (alias export $host "send-user-notification-request" (type $request))
            (alias export $host "send-user-notification-response" (type $response))
            (export "send-user-notification-request" (type $request))
            (export "send-user-notification-response" (type $response))
            (alias export $host "notifications-send-user-notification" (func $send))
            (core module $memory
                (memory (export "memory") 1)
                (global $heap (mut i32) (i32.const 0))
                (func (export "realloc") (param i32 i32 i32 i32) (result i32)
                    global.get $heap
                    global.get $heap local.get 3 i32.add
                    i32.const 7 i32.add i32.const -8 i32.and
                    global.set $heap))
            (core instance $memory (instantiate $memory))
            (core func $send (canon lower (func $send)
                (memory $memory "memory")))
            (core module $adapter
                (import "host" "send" (func $send (param i32 i32 i32 i32) (result i32)))
                (func (export "send") (param i32 i32 i32 i32) (result i32)
                    local.get 0 local.get 1 local.get 2 local.get 3 call $send))
            (core instance $adapter (instantiate $adapter
                (with "host" (instance (export "send" (func $send))))))
            (func (export "send") (param "request" $request) (result $response)
                (canon lift (core func $adapter "send")
                    (memory $memory "memory")
                    (realloc (func $memory "realloc")))))"""),
        )
        instance = linker.instantiate(store, compiled)
        send = instance.get_func(store, "send")
        assert send is not None
        request: Any = component.Record()
        request.type = notification_type
        request.message = MESSAGE
        response = send(store, request)
        send.post_return(store)
        assert response.queued is True

    await asyncio.to_thread(call_import)

    notification_sender.assert_awaited_once_with(
        *DESTINATIONS[notification_type], MESSAGE, None
    )
