import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from websockets.exceptions import ConnectionClosedOK

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.users import Account
from lnbits.core.services import extensions
from lnbits.core.wasm_ext.api import outbound_websockets as ws
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.core.wasm_ext.wasm import invoke
from lnbits.core.wasm_ext.wasm.config import parse_wasm_extension_config
from tests.helpers import make_installable_extension

URL = "wss://feed.example/stream"
GRANT = ExtensionPermission(id="websocket.connect")


class Socket:
    def __init__(self):
        self.messages = asyncio.Queue()
        self.send = AsyncMock()
        self.close_code = None
        self.close_reason = ""

    async def recv(self):
        message = await self.messages.get()
        if isinstance(message, ConnectionClosedOK):
            raise message
        return message

    async def close(self, code=1000, reason=""):
        self.close_code, self.close_reason = code, reason
        self.messages.put_nowait(ConnectionClosedOK(None, None))


def manifest():
    return {
        "id": "demo",
        "name": "Demo",
        "short_description": "Demo",
        "version": "0.1.0",
        "extension_type": "wasm",
        "wasm": {
            "module": "demo.wasm",
            "exports": [{"name": "receive", "visibility": "event"}],
        },
        "events": {"onWebSocket": "receive"},
        "permissions": [{"id": "websocket.connect"}],
    }


def host(user: str | None = "alice", context: str = "user", extension_id: str = "demo"):
    return ExtensionAPIHost(
        ExtensionHostAPI(
            extension_id,
            [GRANT],
            user_id=user,
            context=context,
            owner_id=None if user else f"extension:{extension_id}",
        )
    )


@pytest.fixture
async def peer(settings, mocker):
    settings.lnbits_admin_users = ["alice", "bob"]
    settings.lnbits_running = True
    settings.lnbits_extensions_deactivate_all = False
    installed = make_installable_extension("demo", admin_only=True)
    installed.permissions = [GRANT]
    config = parse_wasm_extension_config("demo", manifest())
    mocker.patch.object(
        ws.core_app_extra.wasm_extension_registry,
        "get",
        return_value=SimpleNamespace(
            id="demo", config=config, exports=config.wasm.exports
        ),
    )
    mocker.patch.object(ws, "get_installed_extension", return_value=installed)
    enabled = SimpleNamespace(active=True, admin_access_granted=False)
    mocker.patch.object(ws, "get_user_extension", return_value=enabled)
    mocker.patch.object(ws, "get_account", side_effect=lambda uid: Account(id=uid))
    callback = mocker.patch.object(invoke, "invoke_wasm_extension_export")
    sockets = []
    connecting, allow_connect = asyncio.Event(), asyncio.Event()
    allow_connect.set()

    @asynccontextmanager
    async def connect(url, *, apply_callback_rules):
        assert url == URL and apply_callback_rules is False
        connecting.set()
        await allow_connect.wait()
        socket = Socket()
        sockets.append(socket)
        try:
            yield socket
        finally:
            await socket.close()

    mocker.patch.object(ws, "safe_websocket", connect)
    yield SimpleNamespace(
        sockets=sockets,
        callback=callback,
        installed=installed,
        enabled=enabled,
        connecting=connecting,
        allow_connect=allow_connect,
    )
    await ws.outbound_websockets.stop()


def test_manifest_and_grant_require_event_export_and_admin_only():
    config = manifest()
    with pytest.raises(ValueError, match="admin-only"):
        validate_wasm_extension_permissions(
            make_installable_extension("demo"), [GRANT], config
        )
    assert validate_wasm_extension_permissions(
        make_installable_extension("demo", admin_only=True), [GRANT], config
    ) == [GRANT]
    config["wasm"]["exports"][0]["visibility"] = "authenticated"
    with pytest.raises(ValueError, match="event export"):
        parse_wasm_extension_config("demo", config)
    config["events"] = {}
    with pytest.raises(ValueError, match="onWebSocket"):
        parse_wasm_extension_config("demo", config)


@pytest.mark.anyio
async def test_concurrent_open_reserves_one_slot_per_extension_and_owner(peer):
    assert ws.settings.wasm_runtime_max_websockets_per_user == 4
    peer.installed.wasm_runtime_limits = {"wasm_runtime_max_websockets_per_user": 1}
    peer.allow_connect.clear()
    user, scheduled = host(), host(context="schedule")
    shared = host(None, "schedule")
    request = {"url": URL, "name": "feed"}
    first = asyncio.create_task(user.invoke("websocket.open", request))
    await asyncio.wait_for(peer.connecting.wait(), 2)
    again = asyncio.create_task(scheduled.invoke("websocket.open", request))
    with pytest.raises(ValueError, match="limit"):
        await scheduled.invoke("websocket.open", {"url": URL})
    with pytest.raises(ValueError, match="different destination"):
        await user.invoke("websocket.open", {"url": URL + "/other", "name": "feed"})
    peer.allow_connect.set()
    alice, duplicate, bob, extension, other = await asyncio.gather(
        first,
        again,
        host("bob").invoke("websocket.open", request),
        shared.invoke("websocket.open", request),
        host(extension_id="other").invoke("websocket.open", request),
    )
    assert alice == duplicate
    assert len({c["connectionId"] for c in (alice, bob, extension, other)}) == 4
    assert len(peer.sockets) == 4
    with pytest.raises(ValueError, match="limit"):
        await shared.invoke("websocket.open", {"url": URL})
    for stranger in (host("bob"), shared, host(extension_id="other")):
        with pytest.raises(ValueError, match="Unknown"):
            await stranger.invoke("websocket.send", {**alice, "text": "hello"})
        with pytest.raises(ValueError, match="Unknown"):
            await stranger.invoke("websocket.close", alice)
    assert await scheduled.invoke("websocket.send", {**alice, "text": "subscribe"}) == {
        "sent": True
    }
    peer.sockets[0].send.assert_awaited_once_with("subscribe")


@pytest.mark.anyio
@pytest.mark.parametrize("user", ["alice", None])
async def test_ordered_text_binary_close_and_callback_identity(peer, user):
    api = host(user, "schedule")
    opened = await api.invoke("websocket.open", {"url": URL})
    conn = ws.outbound_websockets.connections[opened["connectionId"]]
    socket = peer.sockets[0]
    for text in ('{"userId":"bob"}', "second", b"bytes", "discarded"):
        socket.messages.put_nowait(text)
    await asyncio.wait_for(conn.task, 2)
    calls = peer.callback.await_args_list
    assert [call.args for call in calls] == [
        ("demo", "receive", {**opened, "type": "message", "text": '{"userId":"bob"}'}),
        ("demo", "receive", {**opened, "type": "message", "text": "second"}),
        (
            "demo",
            "receive",
            {
                **opened,
                "type": "closed",
                "code": 1003,
                "reason": "Unsupported binary message",
            },
        ),
    ]
    for call in calls:
        assert call.kwargs["context"] == "websocket"
        assert "access_token" not in call.kwargs
        account = call.kwargs["user"]
        assert (account.id if account else None) == user
        assert call.kwargs["owner_id"] == (None if user else "extension:demo")
    assert opened["connectionId"] not in ws.outbound_websockets.connections


@pytest.mark.anyio
async def test_revocation_and_teardown(peer):
    api = host()
    opened = await api.invoke("websocket.open", {"url": URL})
    conn = ws.outbound_websockets.connections[opened["connectionId"]]
    peer.enabled.active = False
    with pytest.raises(PermissionError):
        await api.invoke("websocket.send", {**opened, "text": "hello"})
    peer.sockets[0].messages.put_nowait("revoked")
    await asyncio.wait_for(conn.task, 2)
    peer.callback.assert_not_awaited()
    peer.enabled.active = True
    peer.allow_connect.clear()
    peer.connecting.clear()
    pending = asyncio.create_task(api.invoke("websocket.open", {"url": URL}))
    await asyncio.wait_for(peer.connecting.wait(), 2)
    await ws.outbound_websockets.stop("demo")
    with pytest.raises(ValueError, match="could not be opened"):
        await pending
    assert not ws.outbound_websockets.connections


@pytest.mark.anyio
async def test_close_and_reopen_from_callback(peer):
    api = host()
    request = {"url": URL, "name": "feed"}
    opened = await api.invoke("websocket.open", request)
    conn = ws.outbound_websockets.connections[opened["connectionId"]]
    reconnected = {}

    async def on_event(_ext, _handler, event, **_kwargs):
        background = host(context="websocket")
        if event["type"] == "message":
            await background.invoke("websocket.close", opened)
        else:
            assert event["code"] == 1000
            reconnected.update(await background.invoke("websocket.open", request))

    peer.callback.side_effect = on_event
    peer.sockets[0].messages.put_nowait("close")
    await asyncio.wait_for(conn.task, 2)
    assert reconnected["connectionId"] != opened["connectionId"]
    assert len(peer.sockets) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("event", ["message", "closed"])
@pytest.mark.parametrize(
    "limit",
    [
        "wasm_runtime_max_concurrent_invocations",
        "wasm_runtime_max_concurrent_invocations_per_extension",
        "wasm_runtime_max_concurrent_invocations_per_user",
    ],
)
async def test_busy_runtime_waits_for_message_or_reconnect(peer, mocker, event, limit):
    mocker.stop(peer.callback)
    mocker.patch.object(invoke, "get_installed_extension", return_value=peer.installed)
    mocker.patch.object(extensions, "ensure_wasm_invocation_monitoring_ready")
    mocker.patch.object(extensions, "create_wasm_invocation")
    mocker.patch.object(extensions, "update_wasm_invocation")
    peer.installed.wasm_runtime_limits = {
        limit: 1,
        "wasm_runtime_max_websockets_per_user": 1,
    }
    request = {"url": URL, "name": "feed"}
    opened = await host().invoke("websocket.open", request)
    conn = ws.outbound_websockets.connections[opened["connectionId"]]
    socket = peer.sockets[0]
    reconnected = {}

    def run_guest(_ext, _handler, payload, api, loop, *_args):
        if payload["type"] == "closed":
            reopen = ExtensionAPIHost(api).invoke("websocket.open", request)
            reconnected.update(asyncio.run_coroutine_threadsafe(reopen, loop).result(2))
        return {}

    guest = mocker.patch.object(
        invoke, "_invoke_wasm_extension_export_sync", side_effect=run_guest
    )
    blocker = await extensions.start_wasm_invocation(
        extension_id="demo", export_name="job", user_id="alice"
    )
    waiting = asyncio.Event()
    capacity = extensions._wasm_capacity_changed
    wait = capacity.wait

    async def wait_for_release():
        waiting.set()
        return await wait()

    mocker.patch.object(capacity, "wait", side_effect=wait_for_release)
    try:
        if event == "message":
            socket.messages.put_nowait("first")
            socket.messages.put_nowait("second")
        else:
            await socket.close(1001, "peer left")
        await asyncio.wait_for(waiting.wait(), 2)
        guest.assert_not_called()
        if event == "message":
            assert socket.close_code is None
            assert socket.messages.qsize() == 1
            await socket.close(1001, "peer left")
        else:
            with pytest.raises(ValueError, match="connection limit"):
                await host().invoke("websocket.open", request)
    finally:
        await extensions.finish_wasm_invocation(blocker.id, status="completed")

    await asyncio.wait_for(conn.task, 2)
    delivered = [call.args[2] for call in guest.call_args_list]
    assert delivered[-1] == {
        **opened,
        "type": "closed",
        "code": 1001,
        "reason": "peer left",
    }
    assert [e["text"] for e in delivered[:-1]] == (
        ["first", "second"] if event == "message" else []
    )
    assert reconnected["connectionId"] != opened["connectionId"]


@pytest.mark.anyio
@pytest.mark.parametrize("stop", [False, True])
async def test_pending_callback_respects_revocation_and_stop(peer, mocker, stop):
    mocker.patch.object(extensions, "_wasm_capacity_changed", asyncio.Event())
    busy = extensions.WasmInvocationCapacityError("busy")
    attempted = asyncio.Event()

    async def callback(*_args, **_kwargs):
        attempted.set()
        raise busy

    peer.callback.side_effect = callback
    opened = await host().invoke("websocket.open", {"url": URL})
    conn = ws.outbound_websockets.connections[opened["connectionId"]]
    peer.sockets[0].messages.put_nowait("pending")
    await asyncio.wait_for(attempted.wait(), 2)
    if stop:
        await asyncio.wait_for(ws.outbound_websockets.stop("demo"), 2)
    else:
        peer.enabled.active = False
        extensions.notify_wasm_capacity_changed()
        await asyncio.wait_for(conn.task, 2)
    peer.callback.assert_awaited_once()
    assert not ws.outbound_websockets.connections


@pytest.mark.anyio
async def test_open_requires_authorized_context_permission_and_wss(peer, settings):
    for api in (
        host(None, "user"),
        host(None, "event"),
        host("outsider"),
        ExtensionAPIHost(ExtensionHostAPI("demo", [], user_id="alice")),
    ):
        with pytest.raises(PermissionError):
            await api.invoke("websocket.open", {"url": URL})
    for url in (
        "ws://feed.example",
        "https://feed.example",
        "wss://u:p@feed.example",
        "wss://feed.example/#fragment",
    ):
        with pytest.raises(ValueError):
            await host().invoke("websocket.open", {"url": url})
    peer.installed.meta.installed_release.admin_only = False
    with pytest.raises(PermissionError):
        await host().invoke("websocket.open", {"url": URL})
    settings.lnbits_admin_extensions = ["demo"]
    peer.installed.permissions = []
    with pytest.raises(PermissionError):
        await host().invoke("websocket.open", {"url": URL})
    assert not peer.sockets


@pytest.mark.anyio
async def test_cancelled_open_releases_only_unclaimed_connection(peer):
    api = host()
    request = {"url": URL, "name": "feed"}
    peer.allow_connect.clear()
    abandoned = asyncio.create_task(api.invoke("websocket.open", request))
    await asyncio.wait_for(peer.connecting.wait(), 2)
    conn = next(iter(ws.outbound_websockets.connections.values()))
    abandoned.cancel()
    with pytest.raises(asyncio.CancelledError):
        await abandoned
    await asyncio.gather(conn.task, return_exceptions=True)
    assert not ws.outbound_websockets.connections

    peer.connecting.clear()
    first = asyncio.create_task(api.invoke("websocket.open", request))
    await asyncio.wait_for(peer.connecting.wait(), 2)
    second = asyncio.create_task(api.invoke("websocket.open", request))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    peer.allow_connect.set()
    assert (await second)["connectionId"] in ws.outbound_websockets.connections
    assert len(peer.sockets) == 1


@pytest.mark.anyio
async def test_failed_handshake_releases_reservation(peer, mocker):
    request = {"url": URL, "name": "feed"}
    api = host()
    original = ws.safe_websocket
    mocker.patch.object(ws, "safe_websocket", side_effect=OSError("private detail"))
    with pytest.raises(ValueError, match="^Outbound WebSocket could not be opened.$"):
        await api.invoke("websocket.open", request)
    assert not ws.outbound_websockets.connections
    mocker.patch.object(ws, "safe_websocket", original)
    assert (await api.invoke("websocket.open", request))["connectionId"]


@pytest.mark.anyio
async def test_admin_access_changes_close_idle_sockets(peer, settings):
    settings.lnbits_admin_only_extensions = {"demo"}
    _, bob, shared = await asyncio.gather(
        *(
            api.invoke("websocket.open", {"url": URL})
            for api in (host(), host("bob"), host(None, "schedule"))
        )
    )
    settings.lnbits_admin_users = ["bob"]
    await ws.outbound_websockets.apply_admin_settings()
    assert set(ws.outbound_websockets.connections) == {
        bob["connectionId"],
        shared["connectionId"],
    }
    settings.lnbits_admin_only_extensions = set()
    await ws.outbound_websockets.apply_admin_settings()
    assert not ws.outbound_websockets.connections


@pytest.mark.anyio
async def test_assigned_user_and_aggregate_socket_limits(peer, settings):
    settings.lnbits_admin_only_extensions = {"demo"}
    settings.lnbits_admin_users = ["bob"]
    settings.lnbits_wasm_max_websockets = 2
    peer.installed.wasm_runtime_limits = {
        "wasm_runtime_max_websockets_per_extension": 1
    }
    peer.enabled.admin_access_granted = True
    peer.allow_connect.clear()
    request = {"url": URL, "name": "bot"}
    first = asyncio.create_task(host().invoke("websocket.open", request))
    await asyncio.wait_for(peer.connecting.wait(), 2)
    with pytest.raises(ValueError, match="limit"):
        await host("bob").invoke("websocket.open", request)
    peer.allow_connect.set()
    alice = await first
    await host("bob", extension_id="other").invoke("websocket.open", request)
    with pytest.raises(ValueError, match="limit"):
        await host("bob", extension_id="third").invoke("websocket.open", request)
    await ws.outbound_websockets.apply_admin_settings()
    assert alice["connectionId"] in ws.outbound_websockets.connections
    peer.enabled.admin_access_granted = False
    await ws.outbound_websockets.apply_admin_settings()
    assert alice["connectionId"] not in ws.outbound_websockets.connections
    with pytest.raises(PermissionError):
        await host().invoke("websocket.open", request)
