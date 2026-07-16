from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.views.extension_websocket_api import extension_websocket_connect


@pytest.mark.anyio
async def test_extension_websocket_api_delegates_installed_wasm_subscription(mocker):
    websocket = AsyncMock()
    conn = SimpleNamespace()
    installed_ext = SimpleNamespace(
        active=True,
        is_wasm=True,
        permissions=[ExtensionPermission(id="websocket.subscribe")],
    )
    mocker.patch(
        "lnbits.core.views.extension_websocket_api.get_installed_extension",
        AsyncMock(return_value=installed_ext),
    )
    connect = mocker.patch(
        "lnbits.core.views.extension_websocket_api."
        "wasm_extension_websocket_hub.connect",
        AsyncMock(return_value=conn),
    )
    listen = mocker.patch(
        "lnbits.core.views.extension_websocket_api."
        "wasm_extension_websocket_hub.listen",
        AsyncMock(),
    )

    await extension_websocket_connect(websocket, "demoext", "room-1")

    websocket.close.assert_not_awaited()
    connect.assert_awaited_once_with("demoext", "room-1", websocket)
    listen.assert_awaited_once_with(conn)


@pytest.mark.anyio
async def test_extension_websocket_api_rejects_missing_subscribe_permission(mocker):
    websocket = AsyncMock()
    installed_ext = SimpleNamespace(active=True, is_wasm=True, permissions=[])
    mocker.patch(
        "lnbits.core.views.extension_websocket_api.get_installed_extension",
        AsyncMock(return_value=installed_ext),
    )

    await extension_websocket_connect(websocket, "demoext", "room-1")

    websocket.close.assert_awaited_once()
