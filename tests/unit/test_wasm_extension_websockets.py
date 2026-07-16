from typing import cast

import pytest
from fastapi import WebSocket

from lnbits.core.wasm_ext.api.websockets import (
    WasmExtensionWebsocketHub,
    WasmExtensionWebsocketRateLimitError,
)


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent: list[str] = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, data: str):
        self.sent.append(data)


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
