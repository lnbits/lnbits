from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.views.websocket_api import (
    extension_authoritative_channel_connect,
    extension_websocket_connect,
)


@pytest.mark.anyio
async def test_wasm_extension_websocket_delegates_installed_wasm_subscription(mocker):
    websocket = AsyncMock()
    conn = SimpleNamespace()
    installed_ext = SimpleNamespace(
        active=True,
        is_wasm=True,
        permissions=[ExtensionPermission(id="websocket.subscribe")],
    )
    mocker.patch(
        "lnbits.core.views.websocket_api.get_installed_extension",
        AsyncMock(return_value=installed_ext),
    )
    connect = mocker.patch(
        "lnbits.core.views.websocket_api.wasm_extension_websocket_hub.connect",
        AsyncMock(return_value=conn),
    )
    listen = mocker.patch(
        "lnbits.core.views.websocket_api.wasm_extension_websocket_hub.listen",
        AsyncMock(),
    )

    await extension_websocket_connect(websocket, "demoext", "room-1")

    websocket.close.assert_not_awaited()
    connect.assert_awaited_once_with("demoext", "room-1", websocket)
    listen.assert_awaited_once_with(conn)


@pytest.mark.anyio
async def test_wasm_extension_websocket_rejects_missing_subscribe_permission(mocker):
    websocket = AsyncMock()
    installed_ext = SimpleNamespace(active=True, is_wasm=True, permissions=[])
    mocker.patch(
        "lnbits.core.views.websocket_api.get_installed_extension",
        AsyncMock(return_value=installed_ext),
    )

    await extension_websocket_connect(websocket, "demoext", "room-1")

    websocket.close.assert_awaited_once()


@pytest.mark.anyio
async def test_authoritative_websocket_requires_both_installed_permissions(mocker):
    websocket = AsyncMock()
    mocker.patch(
        "lnbits.core.views.websocket_api.get_installed_extension",
        AsyncMock(
            return_value=SimpleNamespace(
                active=True,
                is_wasm=True,
                permissions=[ExtensionPermission(id="websocket.subscribe")],
            )
        ),
    )

    await extension_authoritative_channel_connect(websocket, "demoext", "room-1")

    websocket.close.assert_awaited_once()


@pytest.mark.anyio
async def test_authoritative_websocket_delegates_granted_channel(mocker):
    websocket = AsyncMock()
    channel = SimpleNamespace(owner_context=SimpleNamespace(table="rooms"))
    extension = SimpleNamespace(
        config=SimpleNamespace(authoritative_channel=channel)
    )
    installed = SimpleNamespace(
        active=True,
        is_wasm=True,
        permissions=[
            ExtensionPermission(id="websocket.authoritative"),
            ExtensionPermission(id="websocket.subscribe"),
        ],
    )
    mocker.patch(
        "lnbits.core.views.websocket_api.get_installed_extension",
        AsyncMock(return_value=installed),
    )
    mocker.patch(
        "lnbits.core.views.websocket_api.core_app_extra.wasm_extension_registry.get",
        return_value=extension,
    )
    mocker.patch(
        "lnbits.core.views.websocket_api.storage_get_row_owner_id",
        AsyncMock(return_value="owner-hash"),
    )
    mocker.patch(
        "lnbits.core.views.websocket_api.get_wasm_runtime_limits_for_extension",
        AsyncMock(return_value={"wasm_runtime_max_execution_ms": 1000}),
    )
    serve = mocker.patch(
        "lnbits.core.views.websocket_api.wasm_extension_websocket_hub.serve_authoritative_channel",
        AsyncMock(),
    )

    await extension_authoritative_channel_connect(websocket, "demoext", "room-1")

    websocket.close.assert_not_awaited()
    serve.assert_awaited_once_with(
        extension,
        "room-1",
        websocket,
        owner_id="owner-hash",
        limits={"wasm_runtime_max_execution_ms": 1000},
    )
