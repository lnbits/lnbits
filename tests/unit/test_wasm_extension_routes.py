from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import HTTPException, Request

from lnbits.core.wasm_ext.routes.api import (
    WasmRequestBodyTooLargeError,
    WasmRoutePayload,
    _read_api_payload,
    _read_json_object_with_size,
    _wasm_extension_api_export,
    _wasm_route_owner_id,
)
from lnbits.core.wasm_ext.routes.assets import (
    _reject_html_like_wasm_static_asset,
    _wasm_extension_core_asset_response,
)
from lnbits.core.wasm_ext.routes.security import (
    consume_wasm_extension_frame_token,
    wasm_extension_frame_csp,
    wasm_extension_frame_url,
)
from lnbits.core.wasm_ext.routes.ui import (
    _match_wasm_extension_ui_route,
    _wasm_extension_bridge_api_routes,
    _wasm_extension_entrypoint,
)
from lnbits.core.wasm_ext.wasm.config import parse_wasm_extension_config
from lnbits.core.wasm_ext.wasm.loader import WasmExtension


@pytest.mark.anyio
async def test_wasm_json_reader_rejects_large_content_length_without_reading():
    request = _FakeRequest([b"{}"], content_length="11")

    with pytest.raises(WasmRequestBodyTooLargeError, match="11 bytes"):
        await _read_json_object_with_size(cast(Request, request), max_body_bytes=10)

    assert request.stream_started is False


@pytest.mark.anyio
async def test_wasm_json_reader_rejects_large_stream_without_content_length():
    request = _FakeRequest([b'{"value":"', b"x" * 20, b'"}'])

    with pytest.raises(WasmRequestBodyTooLargeError):
        await _read_json_object_with_size(cast(Request, request), max_body_bytes=16)

    assert request.stream_started is True


@pytest.mark.anyio
async def test_wasm_api_payload_records_actual_body_bytes():
    body = b'{"amount":21}'
    request = _FakeRequest(
        [body],
        path_params={"invoice_id": "abc"},
        query_params={"include_paid": "true"},
    )

    payload = await _read_api_payload(
        cast(Request, request),
        {"invoice_id": "invoiceId"},
        max_body_bytes=100,
    )

    assert payload.data == {
        "invoiceId": "abc",
        "includePaid": "true",
        "amount": 21,
    }
    assert payload.request_bytes == len(body)


def test_wasm_api_export_visibility_is_enforced(tmp_path: Path):
    extension = _wasm_extension(tmp_path)

    assert _wasm_extension_api_export(extension, "render") == "render"
    assert _wasm_extension_api_export(extension, "private_render") == "private_render"
    with pytest.raises(PermissionError, match="not callable over HTTP"):
        _wasm_extension_api_export(extension, "on_invoice_paid")
    with pytest.raises(KeyError, match="has no export"):
        _wasm_extension_api_export(extension, "missing")


def test_wasm_ui_entrypoint_rejects_escape_static_and_non_html(tmp_path: Path):
    extension = _wasm_extension(tmp_path)
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "index.txt").write_text("text", encoding="utf-8")
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "index.html").write_text("<html></html>", encoding="utf-8")

    assert (
        _wasm_extension_entrypoint(extension, "index.html")
        == (tmp_path / "index.html").resolve()
    )
    with pytest.raises(ValueError, match="escapes extension root"):
        _wasm_extension_entrypoint(extension, "../outside.html")
    with pytest.raises(ValueError, match="must not be inside the static"):
        _wasm_extension_entrypoint(extension, "static/index.html")
    with pytest.raises(ValueError, match="must be an HTML file"):
        _wasm_extension_entrypoint(extension, "index.txt")


def test_wasm_frame_token_is_one_time_and_user_bound(tmp_path: Path):
    extension = _wasm_extension(tmp_path)
    frame_path = "/ext-frame/demoext/0"
    frame_url = wasm_extension_frame_url(extension, frame_path, "user-1")
    token = frame_url.split("frame_token=", 1)[1]

    with pytest.raises(HTTPException) as wrong_user:
        consume_wasm_extension_frame_token(
            _request_with_query(token),
            extension,
            frame_path,
            "user-2",
        )
    assert wrong_user.value.status_code == 404

    consume_wasm_extension_frame_token(
        _request_with_query(token),
        extension,
        frame_path,
        "user-1",
    )
    with pytest.raises(HTTPException) as reused:
        consume_wasm_extension_frame_token(
            _request_with_query(token),
            extension,
            frame_path,
            "user-1",
        )
    assert reused.value.status_code == 404


def test_wasm_frame_csp_is_locked_to_extension_assets(tmp_path: Path):
    csp = wasm_extension_frame_csp(
        _request_with_query("token"),
        _wasm_extension(tmp_path),
    )

    assert "sandbox allow-scripts" in csp
    assert "default-src 'none'" in csp
    assert "connect-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "http://testserver/ext-assets/demoext/" in csp


def test_wasm_ui_route_matching_and_bridge_public_api_filtering(tmp_path: Path):
    extension = _wasm_extension(tmp_path)

    matched = _match_wasm_extension_ui_route(extension, "/ext/demo/abc")
    public_routes = _wasm_extension_bridge_api_routes(extension, public=True)
    private_routes = _wasm_extension_bridge_api_routes(extension, public=False)

    assert matched["auth"] == "user"
    assert matched["route_params"] == {"item_id": "abc"}
    assert public_routes == [
        {
            "method": "GET",
            "path": "/api/v1/ext/demoext/public/{item_id}",
            "pattern": "^/api/v1/ext/demoext/public/[^/]+$",
        }
    ]
    assert {route["path"] for route in private_routes} == {
        "/api/v1/ext/demoext/public/{item_id}",
        "/api/v1/ext/demoext/private/{item_id}",
    }


@pytest.mark.anyio
async def test_wasm_api_route_owner_context_uses_configured_storage_row(
    tmp_path: Path, mocker
):
    extension = _wasm_extension(tmp_path)
    route_config = parse_wasm_extension_config(
        "demoext",
        {
            "id": "demoext",
            "name": "Demo",
            "short_description": "Demo extension",
            "version": "1.0.0",
            "extension_type": "wasm",
            "wasm": {
                "module": "extension.wasm",
                "exports": [{"name": "finish", "visibility": "public"}],
            },
            "api_routes": [
                {
                    "method": "POST",
                    "path": "/games/{game_id}/finish",
                    "export": "finish",
                    "auth": "public",
                    "path_params": {"game_id": "gameId"},
                    "ownerContext": {"table": "games", "idParam": "gameId"},
                }
            ],
        },
    ).api_routes[0]
    owner_lookup = mocker.patch(
        "lnbits.core.wasm_ext.routes.api.storage_get_row_owner_id",
        mocker.AsyncMock(return_value="owner-1"),
    )

    owner_id = await _wasm_route_owner_id(
        extension,
        route_config,
        WasmRoutePayload({"gameId": "game-1"}, request_bytes=10),
    )

    assert owner_id == "owner-1"
    owner_lookup.assert_awaited_once_with("demoext", "games", "game-1")


def test_wasm_static_core_assets_and_html_like_text_assets_are_guarded(tmp_path: Path):
    response = _wasm_extension_core_asset_response("_lnbits/material-icons.css")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"

    for path in ["_lnbits/../bundle.min.css", "_lnbits/missing.css"]:
        with pytest.raises(HTTPException) as exc_info:
            _wasm_extension_core_asset_response(path)
        assert exc_info.value.status_code == 404

    script_path = tmp_path / "app.js"
    script_path.write_text("<script>alert(1)</script>", encoding="utf-8")
    with pytest.raises(HTTPException) as html_like:
        _reject_html_like_wasm_static_asset(script_path)
    assert html_like.value.status_code == 404


class _FakeRequest:
    method = "POST"

    def __init__(
        self,
        chunks: list[bytes],
        *,
        content_length: str | None = None,
        path_params: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> None:
        self._chunks = chunks
        self.headers: dict[str, str] = {}
        if content_length is not None:
            self.headers["content-length"] = content_length
        self.path_params = path_params or {}
        self.query_params = query_params or {}
        self.stream_started = False

    async def stream(self) -> AsyncIterator[bytes]:
        self.stream_started = True
        for chunk in self._chunks:
            yield chunk


def _wasm_extension(root_path: Path) -> WasmExtension:
    config = parse_wasm_extension_config(
        "demoext",
        {
            "id": "demoext",
            "name": "Demo",
            "short_description": "Demo extension",
            "version": "1.0.0",
            "extension_type": "wasm",
            "wasm": {
                "module": "extension.wasm",
                "exports": [
                    {"name": "render", "visibility": "public"},
                    {"name": "private_render", "visibility": "authenticated"},
                    {"name": "on_invoice_paid", "visibility": "event"},
                ],
            },
            "ui_routes": [
                {
                    "path": "/demo/{item_id}",
                    "entrypoint": "index.html",
                    "auth": "user",
                }
            ],
            "api_routes": [
                {
                    "method": "GET",
                    "path": "/public/{item_id}",
                    "export": "render",
                    "auth": "public",
                },
                {
                    "method": "POST",
                    "path": "/private/{item_id}",
                    "export": "private_render",
                    "auth": "user",
                },
            ],
        },
    )
    return WasmExtension(
        id="demoext",
        name="Demo",
        version="1.0.0",
        root_path=root_path,
        module_path=root_path / "extension.wasm",
        wit_path=None,
        world="",
        exports=config.wasm.exports,
        config=config,
    )


def _request_with_query(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": "/ext-frame/demoext/0",
            "query_string": f"frame_token={token}".encode(),
            "headers": [],
        }
    )
