import asyncio
import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from lnbits.core.wasm_ext.api.websockets import (
    WasmAuthoritativeChannelConnection,
    WasmExtensionWebsocketHub,
    WasmExtensionWebsocketRateLimitError,
)
from lnbits.core.wasm_ext.wasm.loader import WasmExtension


class FakeWebSocket:
    def __init__(
        self,
        received: list[str] | None = None,
        send_error: Exception | None = None,
    ):
        self.accepted = False
        self.sent: list[str] = []
        self.closed: int | None = None
        self.received = list(received or [])
        self.send_error = send_error

    async def accept(self):
        self.accepted = True

    async def send_text(self, data: str):
        if self.send_error:
            raise self.send_error
        self.sent.append(data)

    async def receive_text(self):
        if self.received:
            return self.received.pop(0)
        raise WebSocketDisconnect()

    async def close(self, code: int = 1000):
        self.closed = code


@pytest.mark.anyio
async def test_wasm_extension_websocket_hub_publishes_to_matching_channel():
    hub = WasmExtensionWebsocketHub()
    matching = FakeWebSocket()
    other_item = FakeWebSocket()
    other_extension = FakeWebSocket()

    await hub.connect("demoext", "room-1", cast(WebSocket, matching))
    await hub.connect("demoext", "room-2", cast(WebSocket, other_item))
    await hub.connect("otherext", "room-1", cast(WebSocket, other_extension))

    await hub.publish(
        "demoext",
        "room-1",
        '{"message":"Hello"}',
        max_messages_per_second=10,
    )

    assert matching.accepted is True
    assert matching.sent == ['{"message":"Hello"}']
    assert other_item.sent == []
    assert other_extension.sent == []


@pytest.mark.anyio
async def test_wasm_extension_websocket_hub_prunes_stale_publish_connections():
    hub = WasmExtensionWebsocketHub()
    stale = FakeWebSocket(send_error=RuntimeError("websocket closed"))
    active = FakeWebSocket()

    await hub.connect("demoext", "room-1", cast(WebSocket, stale))
    await hub.connect("demoext", "room-1", cast(WebSocket, active))

    await hub.publish(
        "demoext",
        "room-1",
        '{"message":"Hello"}',
        max_messages_per_second=10,
    )

    assert active.sent == ['{"message":"Hello"}']
    assert hub.get_connections("demoext", "room-1")[0].websocket == active


@pytest.mark.anyio
async def test_authoritative_send_awaits_failed_connection_cleanup(mocker):
    hub = WasmExtensionWebsocketHub()
    connection = SimpleNamespace(
        websocket=FakeWebSocket(send_error=RuntimeError("websocket closed")),
        outgoing=asyncio.Queue(maxsize=1),
    )
    disconnect = mocker.patch.object(hub, "disconnect_authoritative", AsyncMock())
    sender = asyncio.create_task(hub._send_authoritative_queue(connection))

    await hub._send_authoritative(connection, '{"type":"state"}')
    await sender

    disconnect.assert_awaited_once_with(connection)


@pytest.mark.anyio
async def test_authoritative_send_closes_slow_subscriber_when_queue_is_full(mocker):
    hub = WasmExtensionWebsocketHub()
    websocket = FakeWebSocket()
    connection = SimpleNamespace(
        websocket=websocket,
        outgoing=asyncio.Queue(maxsize=1),
    )
    connection.outgoing.put_nowait("queued")
    disconnect = mocker.patch.object(hub, "disconnect_authoritative", AsyncMock())

    assert not await hub._send_authoritative(connection, '{"type":"state"}')
    await asyncio.gather(*hub.closing_tasks)

    assert websocket.closed == 1013
    disconnect.assert_awaited_once_with(connection)


@pytest.mark.anyio
async def test_authoritative_overflow_does_not_wait_for_slow_close(mocker):
    hub = WasmExtensionWebsocketHub()
    closing = asyncio.Event()
    finish_close = asyncio.Event()

    async def slow_close(code):
        closing.set()
        await finish_close.wait()

    slow = SimpleNamespace(
        websocket=SimpleNamespace(close=slow_close),
        outgoing=asyncio.Queue(maxsize=1),
    )
    healthy = SimpleNamespace(outgoing=asyncio.Queue(maxsize=1))
    slow.outgoing.put_nowait("queued")
    disconnect = mocker.patch.object(hub, "disconnect_authoritative", AsyncMock())
    try:
        assert not await asyncio.wait_for(hub._send_authoritative(slow, "state"), 0.2)
        assert await hub._send_authoritative(healthy, "state")
        assert healthy.outgoing.get_nowait() == "state"
        await asyncio.wait_for(closing.wait(), 0.2)
        disconnect.assert_awaited_once_with(slow)
    finally:
        finish_close.set()
        await asyncio.gather(*hub.closing_tasks)


@pytest.mark.anyio
async def test_authoritative_close_has_a_timeout(mocker):
    hub = WasmExtensionWebsocketHub()
    cancelled = asyncio.Event()

    async def blocked_close(code):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    mocker.patch(
        "lnbits.core.wasm_ext.api.websockets._AUTHORITATIVE_CLOSE_TIMEOUT_SECONDS",
        0.01,
    )
    await asyncio.wait_for(hub._close(SimpleNamespace(close=blocked_close), 1013), 0.2)
    assert cancelled.is_set()


@pytest.mark.anyio
async def test_authoritative_disconnect_during_send_preserves_queue_cleanup(mocker):
    hub = WasmExtensionWebsocketHub()
    sending = asyncio.Event()

    async def blocked_send(data):
        sending.set()
        await asyncio.Event().wait()

    connection = SimpleNamespace(
        extension=SimpleNamespace(
            id="demoext",
            config=SimpleNamespace(authoritative_channel=None),
        ),
        room_id="room",
        connection_id="connection",
        websocket=SimpleNamespace(send_text=blocked_send),
        sender_task=None,
        outgoing=None,
    )
    mocker.patch(
        "lnbits.core.wasm_ext.api.websockets.release_authoritative_connection",
        AsyncMock(),
    )
    hub.authoritative_connections.append(connection)
    hub.authoritative_tasks[("demoext", "room")] = (asyncio.current_task(),)
    hub._start_authoritative_sender(connection)
    sender = connection.sender_task
    outgoing = connection.outgoing
    try:
        await hub._send_authoritative(connection, "state")
        await asyncio.wait_for(sending.wait(), 0.2)
        await hub.disconnect_authoritative(connection)
        await sender
        await asyncio.wait_for(outgoing.join(), 0.2)
        assert connection.outgoing is None
        assert not hub.authoritative_connections
        assert not hub.authoritative_tasks
    finally:
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)


@pytest.mark.anyio
async def test_authoritative_disconnect_awaits_other_room_tasks(mocker):
    hub = WasmExtensionWebsocketHub()
    started = asyncio.Event()
    finished = asyncio.Event()

    async def delayed_cancel():
        try:
            started.set()
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.01)
            finished.set()

    connection = SimpleNamespace(
        extension=SimpleNamespace(
            id="demoext", config=SimpleNamespace(authoritative_channel=None)
        ),
        room_id="room",
        connection_id="connection",
        websocket=FakeWebSocket(),
        sender_task=None,
        outgoing=None,
    )
    mocker.patch(
        "lnbits.core.wasm_ext.api.websockets.release_authoritative_connection",
        AsyncMock(),
    )
    room_task = asyncio.create_task(delayed_cancel())
    hub.authoritative_connections.append(connection)
    hub.authoritative_tasks[("demoext", "room")] = (asyncio.current_task(), room_task)

    await started.wait()
    await hub.disconnect_authoritative(connection)

    assert room_task.done()
    assert finished.is_set()


@pytest.mark.anyio
async def test_authoritative_renewal_failure_closes_and_disconnects_room(mocker):
    hub = WasmExtensionWebsocketHub()
    channel = SimpleNamespace(persistence="durable")
    connections = [
        SimpleNamespace(
            extension=SimpleNamespace(
                id="demoext", config=SimpleNamespace(authoritative_channel=channel)
            ),
            room_id="room",
            connection_id=f"connection-{index}",
            websocket=FakeWebSocket(),
            sender_task=None,
            outgoing=None,
        )
        for index in range(2)
    ]
    hub.authoritative_connections.extend(connections)
    mocker.patch("lnbits.core.wasm_ext.api.websockets.settings.lnbits_running", True)
    mocker.patch("lnbits.core.wasm_ext.api.websockets.asyncio.sleep", AsyncMock())
    mocker.patch(
        "lnbits.core.wasm_ext.api.websockets.renew_authoritative_connection",
        AsyncMock(side_effect=RuntimeError("sensitive database detail")),
    )
    release = mocker.patch(
        "lnbits.core.wasm_ext.api.websockets.release_authoritative_connection",
        AsyncMock(side_effect=RuntimeError("sensitive database detail")),
    )
    warning = mocker.patch("lnbits.core.wasm_ext.api.websockets.logger.warning")

    await hub._renew_authoritative_connections(connections[0])

    assert not hub.authoritative_connections
    assert [connection.websocket.closed for connection in connections] == [1013, 1013]
    assert release.await_count == 2
    warning.assert_any_call(
        "WASM authoritative connection renewal failed for demoext:room "
        "(RuntimeError)."
    )
    assert all(
        "sensitive database detail" not in str(call) for call in warning.call_args_list
    )


@pytest.mark.anyio
async def test_wasm_extension_websocket_hub_rate_limits_per_channel():
    hub = WasmExtensionWebsocketHub()
    websocket = FakeWebSocket()
    other_websocket = FakeWebSocket()

    await hub.connect("demoext", "room-1", cast(WebSocket, websocket))
    await hub.connect("demoext", "room-2", cast(WebSocket, other_websocket))

    await hub.publish(
        "demoext",
        "room-1",
        '{"message":1}',
        max_messages_per_second=1,
    )
    with pytest.raises(WasmExtensionWebsocketRateLimitError):
        await hub.publish(
            "demoext",
            "room-1",
            '{"message":2}',
            max_messages_per_second=1,
        )

    await hub.publish(
        "demoext",
        "room-2",
        '{"message":3}',
        max_messages_per_second=1,
    )

    assert websocket.sent == ['{"message":1}']
    assert other_websocket.sent == ['{"message":3}']


@pytest.mark.anyio
async def test_wasm_extension_websocket_hub_rebroadcasts_client_messages_to_peers():
    hub = WasmExtensionWebsocketHub()
    sender = FakeWebSocket(received=['{"type":"input","paddle":0.5}'])
    peer = FakeWebSocket()

    conn = await hub.connect("demoext", "game-1", cast(WebSocket, sender))
    await hub.connect("demoext", "game-1", cast(WebSocket, peer))

    await hub.listen(conn)

    assert sender.sent == []
    assert peer.sent == ['{"type":"input","paddle":0.5}']


@pytest.mark.anyio
async def test_authoritative_websocket_token_handshake_returns_canonical_snapshot(
    mocker,
):
    channel = SimpleNamespace(
        authorize_connection="authorize",
        max_active_rooms=2,
        max_queue_depth=4,
        max_events_per_second=10,
        schedule_interval_ms=None,
        on_schedule=None,
    )
    extension = SimpleNamespace(
        id="demoext", config=SimpleNamespace(authoritative_channel=channel)
    )
    websocket = FakeWebSocket(
        received=[json.dumps({"type": "authorize", "token": "session-token"})]
    )
    hub = WasmExtensionWebsocketHub()
    connection = WasmAuthoritativeChannelConnection(
        extension=extension,
        room_id="room-1",
        websocket=cast(WebSocket, websocket),
        owner_id="owner-hash",
        principal_id="principal-hash",
        role="player",
        can_send=True,
        connection_id="connection-1",
        limits={},
        last_client_sequence=3,
        permissions=[],
    )
    state = SimpleNamespace(snapshot={"round": 2}, sequence=7, version=4)
    mocker.patch(
        "lnbits.core.wasm_ext.api.websockets.reserve_authoritative_connection",
        AsyncMock(return_value=True),
    )
    authorize = mocker.patch.object(
        hub,
        "_authorize_authoritative_connection",
        AsyncMock(return_value=(connection, state)),
    )
    mocker.patch.object(hub, "_start_authoritative_room_tasks")
    mocker.patch.object(hub, "listen_authoritative_channel", AsyncMock())
    disconnect = mocker.patch.object(hub, "disconnect_authoritative", AsyncMock())

    await hub.serve_authoritative_channel(
        extension,
        "room-1",
        cast(WebSocket, websocket),
        owner_id="owner-hash",
        limits={
            "wasm_runtime_max_execution_ms": 1000,
            "wasm_runtime_max_authoritative_rooms": 2,
            "wasm_runtime_max_authoritative_connections_per_room": 2,
            "wasm_runtime_max_authoritative_queue_depth": 4,
            "wasm_runtime_max_authoritative_events_per_second": 10,
            "wasm_runtime_max_authoritative_schedule_rate_hz": 1,
        },
    )

    authorize.assert_awaited_once()
    assert authorize.await_args.args[5] == "session-token"
    await asyncio.sleep(0)
    assert json.loads(websocket.sent[0]) == {
        "type": "snapshot",
        "state": {"round": 2},
        "sequence": 7,
        "lastClientSequence": 3,
    }
    connection.sender_task.cancel()
    await asyncio.gather(connection.sender_task, return_exceptions=True)
    disconnect.assert_awaited_once_with(connection)


@pytest.mark.anyio
async def test_ephemeral_control_receipt_does_not_wait_for_owner_ack(mocker):
    owner_started = asyncio.Event()
    owner_finish = asyncio.Event()
    second_received = asyncio.Event()

    class Client(FakeWebSocket):
        async def receive_text(self):
            if len(self.received) == 1:
                await owner_started.wait()
                frame = await super().receive_text()
                second_received.set()
                return frame
            return await super().receive_text()

    channel = SimpleNamespace(
        persistence="ephemeral",
        max_queue_depth=4,
        on_event="onEvent",
        event_fields=["down"],
    )
    extension = SimpleNamespace(
        id="demoext", config=SimpleNamespace(authoritative_channel=channel)
    )
    client = Client(
        received=[
            json.dumps(
                {"sequence": n, "event": {"down": down}, "roomGeneration": "generation"}
            )
            for n, down in [(1, True), (2, False)]
        ]
    )
    conn = WasmAuthoritativeChannelConnection(
        extension=cast(WasmExtension, extension),
        room_id="room",
        websocket=cast(WebSocket, client),
        owner_id="owner",
        principal_id="player",
        role="player",
        can_send=True,
        connection_id="connection",
        limits={},
        last_client_sequence=0,
        permissions=[],
        room_generation="generation",
    )
    applied = []

    async def owner_result(*args, **kwargs):
        owner_started.set()
        await owner_finish.wait()
        applied.append(kwargs["client_sequence"])
        return {"_hostSequence": len(applied)}

    mocker.patch(
        "lnbits.core.wasm_ext.api.websockets.run_authoritative_channel_export",
        side_effect=owner_result,
    )
    hub = WasmExtensionWebsocketHub()
    mocker.patch.object(hub, "_check_authoritative_client_rate")
    send = mocker.patch.object(hub, "_send_authoritative", return_value=True)
    task = asyncio.create_task(hub.listen_authoritative_channel(conn))
    try:
        await asyncio.wait_for(second_received.wait(), 0.5)
        assert conn.last_received_sequence == 2
        assert conn.last_client_sequence == 0 and applied == []
        assert not task.done()
        owner_finish.set()
        await asyncio.wait_for(task, 0.5)
        assert applied == [1, 2]
        assert [
            json.loads(call.args[1])["clientSequence"] for call in send.await_args_list
        ] == [1, 2]
    finally:
        owner_finish.set()
        await asyncio.gather(task, return_exceptions=True)
