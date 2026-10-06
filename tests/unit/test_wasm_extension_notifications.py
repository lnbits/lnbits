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

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.users import UserNotifications
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import SendUserNotificationRequest
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.core.wasm_ext.wasm.host import add_extension_host_imports
from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export
from tests.helpers import make_installable_extension

METHOD = "notifications.send_user"
MESSAGE = "A payment was received for your form."


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


def event_api(**kwargs) -> ExtensionHostAPI:
    return ExtensionHostAPI(
        "forms",
        [METHOD],
        context="event",
        trigger_type="event",
        notification_user_id="recipient-user",
        **kwargs,
    )


@pytest.mark.anyio
async def test_event_notification_uses_saved_user_destinations(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    mocker: MockerFixture,
):
    admin = mocker.patch(
        "lnbits.core.services.notifications.send_admin_notification", AsyncMock()
    )

    result = await ExtensionAPIHost(event_api()).invoke(METHOD, {"message": MESSAGE})

    assert result == {"queued": True}
    notification_sender.assert_awaited_once_with(
        "123456", ["owner@example.com"], ["owner@example.com"], MESSAGE, None
    )
    admin.assert_not_called()


@pytest.mark.anyio
async def test_user_without_notification_destinations_does_not_notify_admins(
    notification_user: SimpleNamespace, notification_sender: AsyncMock
):
    notification_user.extra.notifications = UserNotifications()

    await ExtensionAPIHost(event_api()).invoke(METHOD, {"message": MESSAGE})

    notification_sender.assert_awaited_once_with(None, [], [], MESSAGE, None)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("context", "trigger_type", "user_id"),
    [
        ("user", "http", None),
        ("user", "http", "user-1"),
        ("event", "http", None),
        ("event", "unknown", None),
    ],
)
async def test_notifications_reject_non_event_invocations(
    notification_sender: AsyncMock,
    context: str,
    trigger_type: str,
    user_id: str | None,
):
    api = ExtensionHostAPI(
        "forms",
        [METHOD],
        context=context,
        trigger_type=trigger_type,
        user_id=user_id,
        owner_id="owner-1",
        notification_user_id="recipient-user",
    )

    with pytest.raises(PermissionError):
        await ExtensionAPIHost(api).invoke(METHOD, {"message": MESSAGE})

    notification_sender.assert_not_called()


@pytest.mark.anyio
async def test_notification_requires_install_permission(
    notification_sender: AsyncMock,
):
    api = ExtensionHostAPI(
        "forms",
        [],
        context="event",
        trigger_type="event",
        notification_user_id="recipient-user",
    )

    with pytest.raises(PermissionError, match="missing permission"):
        await ExtensionAPIHost(api).invoke(METHOD, {"message": MESSAGE})

    notification_sender.assert_not_called()


@pytest.mark.anyio
async def test_notification_requires_trusted_event_recipient(
    notification_sender: AsyncMock, mocker: MockerFixture
):
    get_account = mocker.patch("lnbits.core.crud.users.get_account", AsyncMock())
    api = ExtensionHostAPI(
        "forms",
        [METHOD],
        context="event",
        trigger_type="event",
        user_id="interactive-user",
    )

    with pytest.raises(PermissionError, match="no notification recipient"):
        await ExtensionAPIHost(api).invoke(METHOD, {"message": MESSAGE})

    get_account.assert_not_called()
    notification_sender.assert_not_called()


@pytest.mark.anyio
async def test_notification_rejects_missing_or_inactive_user(
    notification_sender: AsyncMock, mocker: MockerFixture
):
    get_account = mocker.patch(
        "lnbits.core.crud.users.get_account", AsyncMock(return_value=None)
    )

    with pytest.raises(ValueError, match="recipient is unavailable"):
        await ExtensionAPIHost(event_api()).invoke(METHOD, {"message": MESSAGE})

    get_account.assert_awaited_once_with("recipient-user")
    notification_sender.assert_not_called()


@pytest.mark.parametrize("message", ["", " ", "\n\t", "x" * 4097])
def test_notification_validates_message(message: str):
    with pytest.raises(ValidationError):
        SendUserNotificationRequest(message=message)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields",
    [
        {"userId": "another-user"},
        {"notificationUserId": "another-user"},
        {"ownerId": "another-owner"},
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
        await ExtensionAPIHost(event_api()).invoke(
            METHOD, {"message": MESSAGE, **fields}
        )

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
    assert "sendUser(input: SendUserNotificationRequest)" in sdk
    assert "Promise<SendUserNotificationResponse>" in sdk
    assert "return host.host.notificationsSendUser(input)" in sdk
    assert "userId" not in sdk
    assert "chatId" not in sdk


@pytest.mark.anyio
@pytest.mark.parametrize("trigger_type", ["event", "http", "unknown"])
async def test_invocation_passes_trusted_trigger_and_recipient_to_host(
    notification_user: SimpleNamespace,
    notification_sender: AsyncMock,
    mocker: MockerFixture,
    trigger_type: str,
):
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
    mocker.patch(
        "lnbits.core.services.extensions.start_wasm_invocation",
        AsyncMock(return_value=SimpleNamespace(id="invocation-1")),
    )
    mocker.patch("lnbits.core.services.extensions.finish_wasm_invocation", AsyncMock())
    mocker.patch("lnbits.core.services.extensions.record_wasm_invocation_host_call")

    def invoke_notification(
        _extension, _export, payload, api, loop, _invocation, _limits
    ):
        assert api.notification_user_id == "recipient-user"
        assert api.user_id is None
        assert api.owner_id == "source-owner"
        return asyncio.run_coroutine_threadsafe(
            ExtensionAPIHost(api).invoke(METHOD, {"message": payload["message"]}), loop
        ).result()

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=invoke_notification,
    )
    call = invoke_wasm_extension_export(
        "forms",
        "on_invoice_paid",
        {
            "message": MESSAGE,
            "triggerType": "event",
            "notificationUserId": "another-user",
        },
        context="event",
        owner_id="source-owner",
        trigger_type=trigger_type,
        notification_user_id="recipient-user",
    )

    if trigger_type == "event":
        assert await call == {"queued": True}
        notification_sender.assert_awaited_once()
    else:
        with pytest.raises(
            PermissionError, match="only allowed during background events"
        ):
            await call
        notification_sender.assert_not_called()


@pytest.mark.anyio
async def test_notification_component_model_import(
    notification_user: SimpleNamespace, notification_sender: AsyncMock
):
    loop = asyncio.get_running_loop()
    api = event_api()

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
                (type $request-def (record (field "message" string)))
                (export "send-user-notification-request"
                    (type $request (eq $request-def)))
                (type $response-def (record (field "queued" bool)))
                (export "send-user-notification-response"
                    (type $response (eq $response-def)))
                (export "notifications-send-user" (func
                    (param "request" $request) (result $response)))))
            (alias export $host "send-user-notification-request" (type $request))
            (alias export $host "send-user-notification-response" (type $response))
            (export "send-user-notification-request" (type $request))
            (export "send-user-notification-response" (type $response))
            (alias export $host "notifications-send-user" (func $send))
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
                (import "host" "send" (func $send (param i32 i32) (result i32)))
                (func (export "send") (param i32 i32) (result i32)
                    local.get 0 local.get 1 call $send))
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
        request.message = MESSAGE
        response = send(store, request)
        send.post_return(store)
        assert response.queued is True

    await asyncio.to_thread(call_import)

    notification_sender.assert_awaited_once_with(
        "123456", ["owner@example.com"], ["owner@example.com"], MESSAGE, None
    )
