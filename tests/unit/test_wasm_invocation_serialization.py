import asyncio
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from lnbits.core.wasm_ext.wasm.config import WasmExtensionExport
from lnbits.core.wasm_ext.wasm.invoke import invoke_wasm_extension_export
from lnbits.helpers import sha256s


@pytest.fixture
def invocation_runtime(mocker):
    exports = [
        WasmExtensionExport(name=name, visibility="public", sync=True)
        for name in ["finish", "first", "later", "other", "queued", "after"]
    ] + [
        WasmExtensionExport(name="unsynced", visibility="public", sync=False),
        WasmExtensionExport(name="default", visibility="public"),
    ]
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._get_registered_extension",
        side_effect=lambda ext_id: SimpleNamespace(id=ext_id, exports=exports),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._active_installed_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(permissions=[])),
    )
    limits = {
        "wasm_runtime_max_execution_ms": 0,
        "wasm_runtime_max_request_bytes": 4096,
    }
    mocker.patch(
        "lnbits.core.services.extensions.resolve_wasm_runtime_limits",
        return_value=limits,
    )
    mocker.patch(
        "lnbits.core.services.extensions.start_wasm_invocation",
        mocker.AsyncMock(side_effect=lambda **kwargs: SimpleNamespace(id=uuid4().hex)),
    )
    mocker.patch(
        "lnbits.core.services.extensions.finish_wasm_invocation", mocker.AsyncMock()
    )
    return limits


@pytest.mark.anyio
async def test_sync_exports_share_owner_lock_across_contexts(
    mocker, invocation_runtime
):
    entered = asyncio.Event()
    release = threading.Event()
    paid = False
    payouts = []

    def payout(_extension, export, _payload, _api, loop, _id, _limits):
        nonlocal paid
        if not paid:
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5)
            payouts.append(export)
            paid = True
        return {"ok": True}

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=payout,
    )
    calls = [
        asyncio.create_task(
            invoke_wasm_extension_export(
                "demo", "finish", context="event", owner_id=sha256s("alice")
            )
        )
    ]
    try:
        await asyncio.wait_for(entered.wait(), 1)
        for index in range(19):
            calls.append(
                asyncio.create_task(
                    invoke_wasm_extension_export(
                        "demo",
                        "later" if index % 2 else "finish",
                        user=SimpleNamespace(id="alice"),
                        context="schedule" if index % 2 else "user",
                    )
                )
            )
        await asyncio.sleep(0.05)
        release.set()
        await asyncio.wait_for(asyncio.gather(*calls), 5)
        assert payouts == ["finish"]
    finally:
        release.set()
        await asyncio.gather(*calls, return_exceptions=True)


@pytest.mark.anyio
@pytest.mark.parametrize("interrupt", ["cancel", "cancel_twice", "timeout"])
async def test_owner_lock_outlives_cancelled_or_timed_out_request(
    mocker, invocation_runtime, interrupt
):
    entered = asyncio.Event()
    stopped = asyncio.Event()
    release = threading.Event()
    later_entered = threading.Event()
    if interrupt == "timeout":
        invocation_runtime["wasm_runtime_max_execution_ms"] = 10

    async def stop(*args, **kwargs):
        stopped.set()

    mocker.patch(
        "lnbits.core.services.extensions.stop_wasm_invocation", side_effect=stop
    )

    def run(_extension, export, _payload, _api, loop, _id, _limits):
        if export == "first":
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(8)
        else:
            later_entered.set()
        return {"ok": True}

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=run,
    )
    first = asyncio.create_task(
        invoke_wasm_extension_export("demo", "first", context="event", owner_id="alice")
    )
    later = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if interrupt in {"cancel", "cancel_twice"}:
            first.cancel()
        await asyncio.wait_for(stopped.wait(), 1)
        if interrupt == "cancel_twice":
            # A second cancellation must not cancel the native thread's wrapper
            # and release the owner lock while its host call is still running.
            first.cancel()
            await asyncio.gather(first, return_exceptions=True)
        later = asyncio.create_task(
            invoke_wasm_extension_export(
                "demo", "later", context="event", owner_id="alice"
            )
        )
        if interrupt == "timeout":
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(first, 3)
        else:
            await asyncio.sleep(0.05)
        assert not later_entered.is_set()
        release.set()
        await asyncio.wait_for(later, 2)
        assert later_entered.is_set()
    finally:
        release.set()
        await asyncio.gather(first, *([later] if later else []), return_exceptions=True)


@pytest.mark.anyio
@pytest.mark.parametrize("context", ["user", "event", "schedule"])
@pytest.mark.parametrize(
    "extension,owner,export",
    [
        ("other", "alice", "other"),
        ("demo", "bob", "other"),
        ("demo", "alice", "unsynced"),
        ("demo", "alice", "default"),
    ],
)
async def test_independent_invocations_are_not_blocked(
    mocker, invocation_runtime, extension, owner, export, context
):
    entered = asyncio.Event()
    release = threading.Event()

    def run(_extension, export, _payload, _api, loop, _id, _limits):
        if export == "first":
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5)
        return {"ok": True}

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=run,
    )
    first = asyncio.create_task(
        invoke_wasm_extension_export(
            "demo",
            "first",
            context=context,
            owner_id=sha256s("alice"),
            user=None if context == "event" else SimpleNamespace(id="alice"),
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert await asyncio.wait_for(
            invoke_wasm_extension_export(
                extension,
                export,
                context=context,
                owner_id=sha256s(owner),
                user=None if context == "event" else SimpleNamespace(id=owner),
            ),
            1,
        ) == {"ok": True}
    finally:
        release.set()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["cancel", "stop"])
async def test_waiting_invocations_are_registered_and_can_be_stopped(
    mocker, invocation_runtime, action
):
    entered = asyncio.Event()
    queued = asyncio.Event()
    release = threading.Event()
    exports = []

    async def start(**kwargs):
        if kwargs["export_name"] == "queued":
            queued.set()
        return SimpleNamespace(id=kwargs["export_name"])

    mocker.patch(
        "lnbits.core.services.extensions.start_wasm_invocation", side_effect=start
    )
    mocker.patch(
        "lnbits.core.services.extensions.wasm_invocation_stop_requested",
        side_effect=lambda invocation_id: action == "stop"
        and invocation_id == "queued",
    )
    finish = mocker.patch(
        "lnbits.core.services.extensions.finish_wasm_invocation", mocker.AsyncMock()
    )

    def run(_extension, export, _payload, _api, loop, _id, _limits):
        exports.append(export)
        if export == "first":
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5)
        return {"ok": True}

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke._invoke_wasm_extension_export_sync",
        side_effect=run,
    )
    first = asyncio.create_task(
        invoke_wasm_extension_export("demo", "first", context="event", owner_id="alice")
    )
    waiting = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        waiting = asyncio.create_task(
            invoke_wasm_extension_export(
                "demo", "queued", context="event", owner_id="alice"
            )
        )
        # Registration must precede acquiring the owner's lock: queued work
        # consumes concurrency capacity and remains visible to admin stop actions.
        await asyncio.wait_for(queued.wait(), 1)
        assert exports == ["first"]
        if action == "cancel":
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting
        release.set()
        await asyncio.wait_for(first, 1)
        if action == "stop":
            with pytest.raises(PermissionError, match="stopped while waiting"):
                await asyncio.wait_for(waiting, 1)
        assert exports == ["first"]
        assert any(call.args[0] == "queued" for call in finish.await_args_list)
        await asyncio.wait_for(
            invoke_wasm_extension_export(
                "demo", "after", context="event", owner_id="alice"
            ),
            1,
        )
        assert exports == ["first", "after"]
    finally:
        release.set()
        await asyncio.gather(
            first, *([waiting] if waiting else []), return_exceptions=True
        )
