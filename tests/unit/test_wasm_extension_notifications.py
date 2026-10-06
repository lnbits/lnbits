import asyncio
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture
from wasmtime import Config, Engine, Store, component, wat2wasm

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.notifications import EmailNotificationMessage
from lnbits.core.services.notifications import process_next_notification
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import SendEmailRequest
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.core.wasm_ext.wasm.host import add_extension_host_imports
from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export
from lnbits.settings import Settings
from tests.helpers import make_installable_extension

EMAIL_REQUEST = {
    "to": ["owner@example.com"],
    "subject": "Form payment received",
    "message": "A payment was received for your form.",
}


@pytest.fixture
def email_queue(settings: Settings, mocker: MockerFixture):
    settings.lnbits_email_notifications_enabled = True
    settings.lnbits_email_notifications_email = "lnbits@example.com"
    settings.lnbits_email_notifications_server = "smtp.example.com"
    queue: asyncio.Queue[EmailNotificationMessage] = asyncio.Queue()
    mocker.patch("lnbits.core.services.notifications.notifications_queue", queue)
    return queue


@pytest.mark.anyio
async def test_event_email_is_queued_and_delivered_with_subject(
    email_queue: asyncio.Queue[EmailNotificationMessage], mocker: MockerFixture
):
    send_mock = mocker.patch(
        "lnbits.core.services.notifications.send_email_notification",
        mocker.AsyncMock(return_value={"status": "ok"}),
    )
    api = ExtensionHostAPI(
        "forms", ["notifications.send_email"], context="event", trigger_type="event"
    )

    result = await ExtensionAPIHost(api).invoke(
        "notifications.send_email", EMAIL_REQUEST
    )

    assert result == {"queued": True}
    assert email_queue.qsize() == 1
    send_mock.assert_not_called()
    await process_next_notification()
    send_mock.assert_awaited_once_with(
        EMAIL_REQUEST["to"], EMAIL_REQUEST["message"], EMAIL_REQUEST["subject"]
    )
    assert email_queue.empty()


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
async def test_email_rejects_non_event_invocations_and_payload_spoofing(
    email_queue: asyncio.Queue[EmailNotificationMessage],
    context: str,
    trigger_type: str,
    user_id: str | None,
):
    api = ExtensionHostAPI(
        "forms",
        ["notifications.send_email"],
        context=context,
        trigger_type=trigger_type,
        user_id=user_id,
        owner_id="owner-1",
    )

    with pytest.raises(PermissionError):
        await ExtensionAPIHost(api).invoke(
            "notifications.send_email",
            {**EMAIL_REQUEST, "triggerType": "event", "context": "event"},
        )

    assert email_queue.empty()


@pytest.mark.anyio
async def test_event_email_requires_install_permission(
    email_queue: asyncio.Queue[EmailNotificationMessage],
):
    api = ExtensionHostAPI("forms", [], context="event", trigger_type="event")

    with pytest.raises(PermissionError, match="missing permission"):
        await ExtensionAPIHost(api).invoke("notifications.send_email", EMAIL_REQUEST)

    assert email_queue.empty()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("lnbits_email_notifications_enabled", False),
        ("lnbits_email_notifications_email", ""),
        ("lnbits_email_notifications_email", "invalid"),
        ("lnbits_email_notifications_server", ""),
    ],
)
async def test_event_email_rejects_unconfigured_smtp(
    email_queue: asyncio.Queue[EmailNotificationMessage],
    settings: Settings,
    setting: str,
    value: Any,
):
    setattr(settings, setting, value)
    api = ExtensionHostAPI(
        "forms", ["notifications.send_email"], context="event", trigger_type="event"
    )

    with pytest.raises(ValueError, match="not configured"):
        await ExtensionAPIHost(api).invoke("notifications.send_email", EMAIL_REQUEST)

    assert email_queue.empty()


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"to": []},
        {"to": ["owner@example.com"] * 11},
        {"to": ["invalid"]},
        {"to": ["a" * 250 + "@example.com"]},
        {"to": ["owner@example.com\r\nBcc: victim@example.com"]},
        {"subject": ""},
        {"subject": " "},
        {"subject": "x" * 257},
        {"subject": "Receipt\r\nBcc: victim@example.com"},
        {"subject": "Receipt\0"},
        {"message": " "},
        {"message": "x" * 65537},
        {"message": "é" * 32769},
    ],
)
def test_email_validates_recipients_headers_and_body(invalid_fields: dict):
    with pytest.raises(ValidationError):
        SendEmailRequest.parse_obj({**EMAIL_REQUEST, **invalid_fields})


def test_email_permission_and_sdk_are_available():
    permission = ExtensionPermission(id="notifications.send_email")
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
    sdk = codegen["generate_typescript_sdk"](method_ids=["notifications.send_email"])
    assert "to: string[]" in sdk
    assert "sendEmail(input: SendEmailRequest): Promise<SendEmailResponse>" in sdk
    assert "return host.host.notificationsSendEmail(input)" in sdk


@pytest.mark.anyio
@pytest.mark.parametrize("trigger_type", ["event", "http", "unknown"])
async def test_invocation_passes_trusted_trigger_to_email_host(
    email_queue: asyncio.Queue[EmailNotificationMessage],
    mocker: MockerFixture,
    trigger_type: str,
):
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._get_registered_extension",
        return_value=SimpleNamespace(id="forms"),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._active_installed_extension",
        mocker.AsyncMock(
            return_value=SimpleNamespace(permissions=["notifications.send_email"])
        ),
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
        mocker.AsyncMock(return_value=SimpleNamespace(id="invocation-1")),
    )
    mocker.patch(
        "lnbits.core.services.extensions.finish_wasm_invocation", mocker.AsyncMock()
    )
    mocker.patch("lnbits.core.services.extensions.record_wasm_invocation_host_call")

    def invoke_email(_extension, _export, payload, api, loop, _invocation, _limits):
        return asyncio.run_coroutine_threadsafe(
            ExtensionAPIHost(api).invoke("notifications.send_email", payload), loop
        ).result()

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=invoke_email,
    )
    call = invoke_wasm_extension_export(
        "forms",
        "on_invoice_paid",
        {**EMAIL_REQUEST, "trigger_type": "event"},
        context="event",
        trigger_type=trigger_type,
    )

    if trigger_type == "event":
        assert await call == {"queued": True}
        assert email_queue.qsize() == 1
    else:
        with pytest.raises(
            PermissionError, match="only allowed during background events"
        ):
            await call
        assert email_queue.empty()


@pytest.mark.anyio
async def test_email_component_model_import(
    email_queue: asyncio.Queue[EmailNotificationMessage],
):
    loop = asyncio.get_running_loop()
    api = ExtensionHostAPI(
        "forms", ["notifications.send_email"], context="event", trigger_type="event"
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
                    (field "to" (list string))
                    (field "subject" string)
                    (field "message" string)))
                (export "send-email-request" (type $request (eq $request-def)))
                (type $response-def (record (field "queued" bool)))
                (export "send-email-response" (type $response (eq $response-def)))
                (export "notifications-send-email" (func
                    (param "request" $request) (result $response)))))
            (alias export $host "send-email-request" (type $request))
            (alias export $host "send-email-response" (type $response))
            (export "send-email-request" (type $request))
            (export "send-email-response" (type $response))
            (alias export $host "notifications-send-email" (func $send))
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
                (import "host" "send" (func $send
                    (param i32 i32 i32 i32 i32 i32) (result i32)))
                (func (export "send")
                    (param i32 i32 i32 i32 i32 i32) (result i32)
                    local.get 0 local.get 1 local.get 2
                    local.get 3 local.get 4 local.get 5 call $send))
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
        request = component.Record()
        for key, value in EMAIL_REQUEST.items():
            setattr(request, key, value)
        response = send(store, request)
        send.post_return(store)
        assert response.queued is True

    await asyncio.to_thread(call_import)

    assert email_queue.qsize() == 1
