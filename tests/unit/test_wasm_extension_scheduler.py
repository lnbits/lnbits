import asyncio
import json
import threading
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture
from wasmtime import Config, Engine, Store, component, wat2wasm

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.scheduler import ScheduledJob
from lnbits.core.services.scheduler import scheduler
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import (
    PayInvoiceRequest,
    PayLnurlRequest,
    StorageGetRequest,
)
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.core.wasm_ext.wasm import scheduler as wasm_scheduler
from lnbits.core.wasm_ext.wasm.host import add_extension_host_imports
from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export
from lnbits.helpers import sha256s
from tests.helpers import make_installable_extension


@pytest.fixture
def account(mocker: MockerFixture):
    account = SimpleNamespace(id="alice", activated=True, is_admin=False)
    mocker.patch(
        "lnbits.core.wasm_ext.api.scheduler.get_account",
        mocker.AsyncMock(return_value=account),
    )
    return account


def schedule() -> ScheduledJob:
    return ScheduledJob(
        id="job-1",
        namespace="extension:demo",
        user_id="alice",
        handler="check",
        cron_expression="*/10 * * * *",
        next_run_at=1800000000,
    )


@pytest.mark.anyio
async def test_scheduler_host_scopes_user_jobs_and_redacts_owner(
    account, mocker: MockerFixture
):
    save = mocker.patch.object(
        scheduler, "save", mocker.AsyncMock(return_value=schedule())
    )
    api = ExtensionHostAPI("demo", ["scheduler.user"], user_id="alice")
    result = await ExtensionAPIHost(api).invoke(
        "scheduler.set",
        {"id": "job-1", "handler": "check", "cronExpression": "*/10 * * * *"},
    )
    assert save.await_args is not None
    assert save.await_args.args[0] == "extension:demo"
    assert save.await_args.kwargs["user_id"] == "alice"
    data = json.loads(result["scheduleJson"])
    assert data["id"] == "job-1"
    assert not {"namespace", "user_id", "lease_token", "lease_until"}.intersection(data)
    for field in ("userId", "namespace"):
        with pytest.raises(ValidationError):
            await ExtensionAPIHost(api).invoke(
                "scheduler.set",
                {"handler": "check", "cronExpression": "* * * * *", field: "other"},
            )


@pytest.mark.anyio
async def test_scheduler_host_requires_separate_extension_grant_and_admin(
    account, mocker: MockerFixture
):
    save = mocker.patch.object(
        scheduler, "save", mocker.AsyncMock(return_value=schedule())
    )
    request = {"scope": "extension", "handler": "check", "cronExpression": "* * * * *"}
    api = ExtensionHostAPI(
        "demo", ["scheduler.user", "scheduler.extension"], user_id="alice"
    )
    with pytest.raises(PermissionError, match="administrator"):
        await ExtensionAPIHost(api).invoke("scheduler.set", request)
    account.is_admin = True
    api.permissions.remove("scheduler.extension")
    with pytest.raises(PermissionError, match="scheduler.extension"):
        await ExtensionAPIHost(api).invoke("scheduler.set", request)
    api.permissions.add("scheduler.extension")
    await ExtensionAPIHost(api).invoke("scheduler.set", request)
    assert save.await_args is not None
    assert save.await_args.kwargs["user_id"] is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("context", "user_id"),
    [("user", None), ("event", "alice"), ("schedule", "alice"), ("schedule", None)],
)
async def test_background_or_public_calls_cannot_manage_jobs(context, user_id):
    api = ExtensionHostAPI(
        "demo",
        ["scheduler.user", "scheduler.extension"],
        user_id=user_id,
        context=context,
    )
    with pytest.raises(PermissionError):
        await ExtensionAPIHost(api).invoke(
            "scheduler.set", {"handler": "check", "cronExpression": "* * * * *"}
        )


@pytest.mark.anyio
async def test_schedule_list_and_delete_remain_scoped_after_permission_revocation(
    account, mocker: MockerFixture
):
    listing = mocker.patch.object(scheduler, "list", mocker.AsyncMock(return_value=[]))
    deletion = mocker.patch.object(
        scheduler, "delete", mocker.AsyncMock(return_value=False)
    )
    api = ExtensionAPIHost(ExtensionHostAPI("demo", [], user_id="alice"))
    await api.invoke("scheduler.list", {})
    await api.invoke("scheduler.delete", {"id": "other-job"})
    listing.assert_awaited_once_with(
        "extension:demo", user_id="alice", limit=100, offset=0
    )
    deletion.assert_awaited_once_with("extension:demo", "other-job", user_id="alice")


@pytest.mark.anyio
@pytest.mark.parametrize("owner", ["alice", None])
async def test_schedule_dispatch_preserves_user_or_global_context(
    owner, mocker: MockerFixture
):
    extension = SimpleNamespace(
        exports=[SimpleNamespace(name="check", visibility="event")]
    )
    mocker.patch.object(
        wasm_scheduler.core_app_extra.wasm_extension_registry,
        "get",
        return_value=extension,
    )
    account = SimpleNamespace(id="alice", activated=True)
    mocker.patch.object(
        wasm_scheduler, "get_account", mocker.AsyncMock(return_value=account)
    )
    invoke = mocker.patch.object(
        wasm_scheduler, "invoke_wasm_extension_export", mocker.AsyncMock()
    )
    job = schedule().copy(update={"user_id": owner})
    await wasm_scheduler.dispatch_wasm_schedule(job)
    assert invoke.await_args is not None
    assert invoke.await_args.args[0:2] == ("demo", "check")
    assert invoke.await_args.args[2]["data"] == {}
    kwargs = invoke.await_args.kwargs
    assert kwargs["user"] is (account if owner else None)
    assert kwargs["context"] == "schedule"
    assert kwargs["trigger_type"] == "schedule"
    assert "access_token" not in kwargs
    extension.exports[0].visibility = "public"
    with pytest.raises(PermissionError):
        await wasm_scheduler.dispatch_wasm_schedule(job)


@pytest.mark.anyio
async def test_user_schedule_storage_uses_owner_and_global_has_no_owner(
    mocker: MockerFixture,
):
    storage = mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_row",
        mocker.AsyncMock(return_value=None),
    )
    api = ExtensionHostAPI(
        "demo", ["ext.storage.read"], user_id="alice", context="schedule"
    )
    await api.storage_get(StorageGetRequest(table="alerts", id="alert-1"))
    assert storage.await_args is not None
    assert storage.await_args.args[-1] == sha256s("alice")
    global_api = ExtensionHostAPI("demo", ["ext.storage.read"], context="schedule")
    with pytest.raises(PermissionError, match="owner context"):
        await global_api.storage_get(StorageGetRequest(table="alerts", id="alert-1"))


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["invoice", "lnurl"])
async def test_scheduled_payments_require_background_grants(
    method, mocker: MockerFixture
):
    wallet = SimpleNamespace(user="alice")
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=wallet)
    )
    pay = mocker.patch("lnbits.core.services.payments.pay_invoice", mocker.AsyncMock())
    api = ExtensionHostAPI(
        "demo", ["wallet.pay_invoice"], user_id="alice", context="schedule"
    )
    if method == "invoice":
        result = await api.wallet_pay_invoice(
            PayInvoiceRequest(
                wallet_id="wallet",
                payment_request="invoice",
                max_sat=None,
                description="",
            )
        )
    else:
        result = await api.wallet_pay_lnurl(
            PayLnurlRequest(
                wallet_id="wallet",
                lnurl="alice@example.com",
                amount=1,
                currency="sat",
                comment=None,
                description="",
                max_sat=None,
            )
        )
    assert not result.ok and "wallet.pay_invoice_background" in (result.error or "")
    pay.assert_not_called()
    api.permissions.add("wallet.pay_invoice_background")
    wallet.user = "bob"
    with pytest.raises(PermissionError):
        if method == "invoice":
            await api.wallet_pay_invoice(
                PayInvoiceRequest(
                    wallet_id="wallet",
                    payment_request="invoice",
                    max_sat=None,
                    description="",
                )
            )
        else:
            await api.wallet_pay_lnurl(
                PayLnurlRequest(
                    wallet_id="wallet",
                    lnurl="bob@example.com",
                    amount=1,
                    currency="sat",
                    comment=None,
                    description="",
                    max_sat=None,
                )
            )


def test_scheduler_permissions_and_sdk_are_discoverable():
    permissions = [
        ExtensionPermission(id="scheduler.user"),
        ExtensionPermission(id="scheduler.extension"),
    ]
    config = {
        "id": "demo",
        "name": "Demo",
        "version": "0.1.0",
        "short_description": "Demo",
        "extension_type": "wasm",
        "wasm": {"module": "extension.wasm"},
        "permissions": [p.dict() for p in permissions],
    }
    extension = make_installable_extension("demo")
    with pytest.raises(ValueError, match="requires permission approval"):
        validate_wasm_extension_permissions(extension, None, config)
    assert (
        validate_wasm_extension_permissions(extension, permissions, config)
        == permissions
    )
    codegen = run_path(
        str(
            Path(__file__).resolve().parents[2]
            / "tools/codegen/extension_sdk_typescript.py"
        )
    )
    sdk = codegen["generate_typescript_sdk"](
        method_ids=["scheduler.set", "scheduler.list", "scheduler.delete"]
    )
    assert "cronExpression: string" in sdk
    assert 'scope?: "user" | "extension"' in sdk
    assert "set(input: ScheduleSetRequest)" in sdk
    assert "userId" not in sdk


@pytest.mark.anyio
async def test_scheduler_component_import(account, mocker: MockerFixture):
    mocker.patch.object(scheduler, "list", mocker.AsyncMock(return_value=[]))
    loop = asyncio.get_running_loop()
    api = ExtensionHostAPI("demo", ["scheduler.user"], user_id="alice")

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
            (import "lnbits:extension/scheduler" (instance $host
                (type $request-def (record (field "scope" string)
                    (field "limit" u32) (field "offset" u32)))
                (export "request" (type $request (eq $request-def)))
                (type $response-def (record (field "schedules-json" string)))
                (export "response" (type $response (eq $response-def)))
                (export "list-schedules" (func (param "request" $request)
                    (result $response)))))
            (alias export $host "request" (type $request))
            (alias export $host "response" (type $response))
            (export "request" (type $request))
            (export "response" (type $response))
            (alias export $host "list-schedules" (func $list))
            (core module $memory
                (memory (export "memory") 1)
                (global $heap (mut i32) (i32.const 0))
                (func (export "realloc") (param i32 i32 i32 i32) (result i32)
                    global.get $heap
                    global.get $heap local.get 3 i32.add
                    i32.const 7 i32.add i32.const -8 i32.and
                    global.set $heap))
            (core instance $memory (instantiate $memory))
            (core func $list (canon lower (func $list)
                (memory $memory "memory") (realloc (func $memory "realloc"))))
            (core module $adapter
                (import "host" "list" (func $list (param i32 i32 i32 i32 i32)))
                (import "host" "realloc" (func $realloc
                    (param i32 i32 i32 i32) (result i32)))
                (func (export "list") (param i32 i32 i32 i32) (result i32)
                    (local $result i32)
                    i32.const 0 i32.const 0 i32.const 4 i32.const 8
                    call $realloc local.set $result
                    local.get 0 local.get 1 local.get 2 local.get 3
                    local.get $result call $list local.get $result))
            (core instance $adapter (instantiate $adapter
                (with "host" (instance (export "list" (func $list))
                    (export "realloc" (func $memory "realloc"))))))
            (func (export "list") (param "request" $request) (result $response)
                (canon lift (core func $adapter "list")
                    (memory $memory "memory")
                    (realloc (func $memory "realloc")))))"""),
        )
        instance = linker.instantiate(store, compiled)
        function = instance.get_func(store, "list")
        assert function
        request: Any = component.Record()
        request.scope = "user"
        request.limit = 100
        request.offset = 0
        response = function(store, request)
        function.post_return(store)
        return getattr(response, "schedules-json")

    assert await asyncio.wait_for(asyncio.to_thread(call_import), 5) == "[]"


@pytest.mark.anyio
@pytest.mark.parametrize("timeout_ms,cancel", [(0, True), (1000, True), (10, False)])
async def test_scheduler_invocation_stops_and_drains_wasm_thread(
    timeout_ms: int, cancel: bool, mocker: MockerFixture
):
    entered = asyncio.Event()
    stop_requested = asyncio.Event()
    exited = threading.Event()
    release = threading.Event()
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._get_registered_extension",
        return_value=SimpleNamespace(id="demo"),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._active_installed_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(permissions=[])),
    )
    mocker.patch(
        "lnbits.core.services.extensions.resolve_wasm_runtime_limits",
        return_value={
            "wasm_runtime_max_execution_ms": timeout_ms,
            "wasm_runtime_max_request_bytes": 4096,
        },
    )
    mocker.patch(
        "lnbits.core.services.extensions.start_wasm_invocation",
        mocker.AsyncMock(return_value=SimpleNamespace(id="invocation")),
    )
    finish = mocker.patch(
        "lnbits.core.services.extensions.finish_wasm_invocation", mocker.AsyncMock()
    )

    async def stop(*args, **kwargs):
        stop_requested.set()
        if cancel:
            release.set()

    stop_mock = mocker.patch(
        "lnbits.core.services.extensions.stop_wasm_invocation", side_effect=stop
    )

    def invoke(_extension, _export, _payload, _api, loop, _id, _limits):
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(timeout=5)
        exited.set()
        return {"ok": True}

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=invoke,
    )
    task = asyncio.create_task(
        invoke_wasm_extension_export("demo", "check", context="schedule")
    )
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            finish.assert_awaited_once_with(
                "invocation", status="stopped", stop_reason="Invocation cancelled."
            )
        else:
            await asyncio.wait_for(stop_requested.wait(), 1)
            # Scheduled invocations must wait beyond the HTTP path's 2s grace
            # period, keeping the schedule claim until the thread really exits.
            await asyncio.sleep(2.1)
            assert not task.done()
            release.set()
            assert await asyncio.wait_for(task, 1) == {"ok": True}
            assert finish.await_args is not None
            assert finish.await_args.kwargs["status"] == "timeout"
        assert exited.is_set()
        stop_mock.assert_awaited_once()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
