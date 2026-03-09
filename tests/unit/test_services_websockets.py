import asyncio

import pytest
from fastapi import WebSocketDisconnect
from pytest_mock.plugin import MockerFixture

from lnbits.core.services.websockets import (
    WebsocketConnectionManager,
    websocket_updater,
)
from lnbits.settings import Settings


class FakeWebSocket:
    def __init__(self, received=None):
        self.received = list(received or [])
        self.accepted = False
        self.sent: list[str] = []

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if self.received:
            value = self.received.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        raise WebSocketDisconnect()

    async def send_text(self, data: str):
        self.sent.append(data)


@pytest.mark.anyio
async def test_websocket_connection_manager_connect_and_send():
    manager = WebsocketConnectionManager()
    websocket = FakeWebSocket()

    conn = await manager.connect("item-1", websocket)
    await manager.send("item-1", "payload")

    assert websocket.accepted is True
    assert manager.has_connection("item-1") is True
    assert manager.get_connections("item-1") == [conn]
    assert websocket.sent == ["payload"]


@pytest.mark.anyio
async def test_websocket_connection_manager_listen_queues_messages_and_disconnects(
    settings: Settings,
):
    manager = WebsocketConnectionManager()
    websocket = FakeWebSocket(["hello", WebSocketDisconnect()])
    conn = await manager.connect("item-2", websocket)
    original_running = settings.lnbits_running
    try:
        settings.lnbits_running = True
        await manager.listen(conn)
    finally:
        settings.lnbits_running = original_running

    assert conn.receive_queue.get_nowait() == "hello"
    assert manager.has_connection("item-2") is False


@pytest.mark.anyio
async def test_websocket_updater_delegates_to_manager(mocker: MockerFixture):
    send = mocker.patch(
        "lnbits.core.services.websockets.websocket_manager.send",
        mocker.AsyncMock(),
    )

    await websocket_updater("item-3", "data")

    send.assert_awaited_once_with("item-3", "data")
