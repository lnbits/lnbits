import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from lnbits.core.wasm_ext.api.websockets import (
    WasmExtensionWebsocketHub,
    WasmExtensionWebsocketRateLimitError,
)


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
    connection = SimpleNamespace(last_client_sequence=3)
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
    assert json.loads(websocket.sent[0]) == {
        "type": "snapshot",
        "state": {"round": 2},
        "sequence": 7,
        "lastClientSequence": 3,
    }
    disconnect.assert_awaited_once_with(connection)
