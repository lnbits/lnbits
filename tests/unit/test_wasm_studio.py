from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from lnbits.core.models.users import Account
from lnbits.core.wasm_ext import studio_security
from lnbits.core.wasm_ext.runtime import StudioExtension, WasmStudioContext
from lnbits.core.wasm_ext.studio_security import (
    WasmStudioMiddleware,
    rewrite_studio_urls,
)


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["anonymous", "user", "admin"])
@pytest.mark.parametrize("root_path", ["", "/lnbits"])
async def test_wasm_studio_websocket_access_requires_admin(
    mocker, tmp_path, role, root_path
):
    studio = _studio(tmp_path)
    mocker.patch.object(studio_security, "get_wasm_studio_context", return_value=studio)
    account = Account(id="admin")
    account_check = mocker.patch.object(
        studio_security, "check_account_exists", AsyncMock(return_value=account)
    )
    admin_check = mocker.patch.object(
        studio_security, "check_admin", AsyncMock(return_value=account)
    )
    if role == "anonymous":
        account_check.side_effect = HTTPException(401, "Authentication required")
    elif role == "user":
        admin_check.side_effect = HTTPException(403, "Admin required")
    downstream = AsyncMock()
    send = AsyncMock()
    scope = {
        "type": "websocket",
        "path": root_path + "/api/v1/ext/ws/demo_hash/room",
        "root_path": root_path,
        "headers": [(b"cookie", b"cookie_access_token=test-session")],
    }
    await WasmStudioMiddleware(downstream)(scope, AsyncMock(), send)
    assert account_check.call_args.args[1] == "test-session"
    if role == "admin":
        downstream.assert_awaited_once()
        send.assert_not_awaited()
    else:
        downstream.assert_not_awaited()
        send.assert_awaited_once_with({"type": "websocket.close", "code": 1008})


def test_wasm_studio_url_rewriting_preserves_other_extensions(tmp_path):
    studio = _studio(tmp_path)
    content = (
        "/ext-assets/demo/app.js /api/v1/ext/demo${path} /ext/demo?key=value "
        "/api/v1/ext/demo_other/run /ext-assets/demo_other/app.js"
    )
    result = rewrite_studio_urls(content, studio, "asset-token")
    assert result == (
        "/ext-assets/demo_hash/asset-token/app.js /api/v1/ext/demo_hash${path} "
        "/ext/demo_hash?key=value /api/v1/ext/demo_other/run "
        "/ext-assets/demo_other/app.js"
    )


def _studio(tmp_path: Path) -> WasmStudioContext:
    return WasmStudioContext(
        source_id="demo",
        user_id="admin",
        extension=StudioExtension(
            id="demo_hash",
            name="Demo",
            version="1",
            active=True,
            workspace_path=tmp_path,
        ),
    )
