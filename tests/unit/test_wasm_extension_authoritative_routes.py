from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.views.extension_api import _wasm_payment_intent_wallet
from lnbits.core.wasm_ext.routes import api as wasm_api
from lnbits.core.wasm_ext.wasm.config import WasmAPIRouteConfig, WasmRouteOwnerContext
from lnbits.helpers import sha256s


@pytest.mark.anyio
async def test_serialized_room_export_requires_runtime_permissions(mocker):
    extension = SimpleNamespace(id="demoext")
    mocker.patch(
        "lnbits.core.wasm_ext.routes.api.get_installed_extension",
        return_value=SimpleNamespace(
            active=True,
            is_wasm=True,
            permissions=[ExtensionPermission(id="websocket.subscribe")],
        ),
    )

    with pytest.raises(PermissionError, match="permission is not granted"):
        await wasm_api._invoke_serialized_room_export(
            extension,
            "serialize",
            _request(),
            _route_config(),
            wasm_api.WasmRoutePayload({"roomId": "room-1"}, 1),
            limits={},
            account=SimpleNamespace(id="user-1"),
            access_token=None,
        )


@pytest.mark.anyio
async def test_serialized_room_export_requires_room_owner(mocker):
    extension = SimpleNamespace(id="demoext")
    mocker.patch(
        "lnbits.core.wasm_ext.routes.api.get_installed_extension",
        return_value=SimpleNamespace(
            active=True,
            is_wasm=True,
            permissions=[
                ExtensionPermission(id="websocket.authoritative"),
                ExtensionPermission(id="websocket.subscribe"),
            ],
        ),
    )
    owner_lookup = mocker.patch(
        "lnbits.core.wasm_ext.routes.api.storage_get_row_owner_id",
        return_value="another-owner",
    )

    with pytest.raises(PermissionError, match="belongs to another user"):
        await wasm_api._invoke_serialized_room_export(
            extension,
            "serialize",
            _request(),
            _route_config(),
            wasm_api.WasmRoutePayload({}, 1),
            limits={},
            account=SimpleNamespace(id="user-1"),
            access_token=None,
        )
    owner_lookup.assert_awaited_once_with("demoext", "rooms", "room-1")


@pytest.mark.anyio
async def test_serialized_room_export_uses_authoritative_queue(mocker):
    extension = SimpleNamespace(id="demoext")
    mocker.patch(
        "lnbits.core.wasm_ext.routes.api.get_installed_extension",
        return_value=SimpleNamespace(
            active=True,
            is_wasm=True,
            permissions=[
                ExtensionPermission(id="websocket.authoritative"),
                ExtensionPermission(id="websocket.subscribe"),
            ],
        ),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.routes.api.storage_get_row_owner_id",
        return_value=sha256s("user-1"),
    )
    invoke = mocker.patch(
        "lnbits.core.wasm_ext.routes.api.run_authoritative_channel_export",
        return_value={"ok": True, "data": {"state": {"round": 2}}},
    )

    result = await wasm_api._invoke_serialized_room_export(
        extension,
        "serialize",
        _request(),
        _route_config(),
        wasm_api.WasmRoutePayload({}, 1),
        limits={"wasm_runtime_max_execution_ms": 1000},
        account=SimpleNamespace(id="user-1"),
        access_token="token",
    )

    assert result["ok"] is True
    args = invoke.await_args
    assert args.args[1] == "room-1"
    assert args.args[2] == sha256s("user-1")
    assert args.args[4]["roomId"] == "room-1"
    assert args.kwargs["action"] == "api"


@pytest.mark.anyio
async def test_public_serialized_room_export_uses_server_owner_context(mocker):
    extension = SimpleNamespace(id="demoext")
    mocker.patch(
        "lnbits.core.wasm_ext.routes.api.get_installed_extension",
        return_value=SimpleNamespace(
            active=True,
            is_wasm=True,
            permissions=[
                ExtensionPermission(id="websocket.authoritative"),
                ExtensionPermission(id="websocket.subscribe"),
            ],
        ),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.routes.api.storage_get_row_owner_id",
        return_value="room-owner",
    )
    invoke = mocker.patch(
        "lnbits.core.wasm_ext.routes.api.run_authoritative_channel_export",
        return_value={"ok": True, "data": {}},
    )
    route_config = _route_config().copy(update={"auth": "public"})

    await wasm_api._invoke_serialized_room_export(
        extension,
        "serialize",
        _request(),
        route_config,
        wasm_api.WasmRoutePayload({}, 1),
        limits={"wasm_runtime_max_execution_ms": 1000},
        account=None,
        access_token=None,
    )

    assert invoke.await_args.args[2] == "room-owner"


def _route_config():
    return WasmAPIRouteConfig(
        method="POST",
        path="/rooms/{room_id}",
        export="serialize",
        auth="user",
        path_params={"room_id": "str"},
        owner_context=WasmRouteOwnerContext(table="rooms", idParam="roomId"),
        serializeRoom=True,
    )


def _request():
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/ext/demoext/rooms/room-1",
            "headers": [],
            "query_string": b"",
            "path_params": {"room_id": "room-1"},
        }
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "account_id,is_admin,wallet_user,allowed",
    [
        ("owner", False, "owner", True),
        ("other", False, "owner", False),
        ("admin", True, "owner", True),
    ],
)
async def test_manual_payment_intent_access_is_wallet_owner_or_admin_only(
    mocker, account_id, is_admin, wallet_user, allowed
):
    wallet = SimpleNamespace(user=wallet_user)
    mocker.patch(
        "lnbits.core.views.extension_api.get_installed_extension",
        AsyncMock(return_value=SimpleNamespace(is_wasm=True)),
    )
    mocker.patch(
        "lnbits.core.views.extension_api.get_wallet",
        AsyncMock(return_value=wallet),
    )

    if allowed:
        assert (
            await _wasm_payment_intent_wallet(
                "demoext", "wallet-1", SimpleNamespace(id=account_id, is_admin=is_admin)
            )
            is wallet
        )
    else:
        with pytest.raises(HTTPException) as error:
            await _wasm_payment_intent_wallet(
                "demoext", "wallet-1", SimpleNamespace(id=account_id, is_admin=is_admin)
            )
        assert error.value.status_code == 403
