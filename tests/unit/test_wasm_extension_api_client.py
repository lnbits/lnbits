from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.wasm_ext.api.models import ExtensionApiRequest
from lnbits.core.wasm_ext.client import extensions as extension_client
from lnbits.settings import Settings


def test_wasm_extension_api_path_validation():
    assert (
        extension_client._extension_api_path("/api/v1/payments?limit=1")
        == "/api/v1/payments?limit=1"
    )

    for path, message in [
        ("https://example.com/api/v1/payments", "relative"),
        ("/wallet", "start with '/api/'"),
        ("/api/v1/payments#frag", "fragment"),
        ("/api/v1/../admin", "traverse"),
        ("/api/v1/%2e%2e/admin", "traverse"),
        ("/api//v1/payments", "invalid"),
    ]:
        with pytest.raises(PermissionError, match=message):
            extension_client._extension_api_path(path)


def test_wasm_extension_api_target_and_access_validation():
    assert extension_client._target_extension_id(" target_ext ") == "target_ext"
    for extension_id in ["", "../admin", "bad.ext"]:
        with pytest.raises(PermissionError, match="invalid target"):
            extension_client._target_extension_id(extension_id)

    assert extension_client._target_extension_access(["target"], "target") == {"read"}
    assert extension_client._target_extension_access(
        [{"id": "target", "access": ["read", "write", "ignored"]}],
        "target",
    ) == {"read", "write"}

    read_request = ExtensionApiRequest(
        extension_id="target",
        method="GET",
        path="/api/v1/demo",
        body=None,
    )
    write_request = ExtensionApiRequest(
        extension_id="target",
        method="POST",
        path="/api/v1/demo",
        body="{}",
    )
    extension_client._require_method_access(
        "caller",
        "target",
        {"read"},
        read_request,
    )
    with pytest.raises(PermissionError, match="cannot write"):
        extension_client._require_method_access(
            "caller",
            "target",
            {"read"},
            write_request,
        )


@pytest.mark.anyio
async def test_wasm_extension_api_request_enforces_auth_policy_and_user_enablement(
    settings: Settings,
    mocker: MockerFixture,
):
    settings.host = "127.0.0.1"
    settings.port = 5000
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_installed_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(active=True)),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_user_active_extensions_ids",
        mocker.AsyncMock(return_value=["target"]),
    )
    client = _FakeAsyncClient(
        _FakeStreamResponse(
            status_code=202,
            headers={"set-cookie": "secret", "x-result": "ok"},
            chunks=[b'{"accepted":true}'],
        )
    )
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.httpx.AsyncClient",
        client.factory,
    )

    response = await extension_client.send_extension_api_request(
        "caller",
        [{"id": "target", "access": ["write"]}],
        "user-id",
        "access-token",
        ExtensionApiRequest(
            extension_id="target",
            method="POST",
            path="/api/v1/run?value=1",
            body="{}",
        ),
        timeout_ms=750,
        max_response_bytes=100,
    )

    assert response.status_code == 202
    assert response.body == '{"accepted":true}'
    assert response.headers == {"x-result": "ok"}
    assert client.kwargs["follow_redirects"] is False
    assert client.kwargs["trust_env"] is False
    assert client.kwargs["timeout"] == 0.75
    assert (
        client.stream_kwargs["url"] == "http://127.0.0.1:5000/target/api/v1/run?value=1"
    )
    assert client.stream_kwargs["headers"] == {"Authorization": "Bearer access-token"}


@pytest.mark.anyio
async def test_wasm_extension_api_request_rejects_missing_auth_and_disabled_targets(
    mocker: MockerFixture,
):
    request = ExtensionApiRequest(
        extension_id="target",
        method="GET",
        path="/api/v1/run",
        body=None,
    )
    with pytest.raises(PermissionError, match="authentication"):
        await extension_client.send_extension_api_request(
            "caller",
            ["target"],
            None,
            "access-token",
            request,
        )
    with pytest.raises(PermissionError, match="access token"):
        await extension_client.send_extension_api_request(
            "caller",
            ["target"],
            "user-id",
            None,
            request,
        )

    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_installed_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(active=False)),
    )
    with pytest.raises(PermissionError, match="not installed or enabled"):
        await extension_client.send_extension_api_request(
            "caller",
            ["target"],
            "user-id",
            "access-token",
            request,
        )

    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_installed_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(active=True)),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_user_active_extensions_ids",
        mocker.AsyncMock(return_value=[]),
    )
    with pytest.raises(PermissionError, match="not active for this user"):
        await extension_client.send_extension_api_request(
            "caller",
            ["target"],
            "user-id",
            "access-token",
            request,
        )


@pytest.mark.anyio
async def test_wasm_extension_api_request_rejects_oversized_body_and_response(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_installed_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(active=True)),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_user_active_extensions_ids",
        mocker.AsyncMock(return_value=["target"]),
    )
    with pytest.raises(ValueError, match="body is too large"):
        await extension_client.send_extension_api_request(
            "caller",
            [{"id": "target", "access": ["write"]}],
            "user-id",
            "access-token",
            ExtensionApiRequest.construct(
                extension_id="target",
                method="POST",
                path="/api/v1/run",
                body="x" * 65_537,
            ),
        )

    with pytest.raises(ValueError, match="response is too large"):
        await extension_client._read_limited_response(
            cast(httpx.Response, _FakeStreamResponse(chunks=[b"12345", b"67890"])),
            max_response_bytes=8,
        )


@pytest.mark.anyio
async def test_wasm_extension_api_request_hides_transport_errors(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_installed_extension",
        mocker.AsyncMock(return_value=SimpleNamespace(active=True)),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.get_user_active_extensions_ids",
        mocker.AsyncMock(return_value=["target"]),
    )
    client = _FakeAsyncClient(_FakeStreamError())
    mocker.patch(
        "lnbits.core.wasm_ext.client.extensions.httpx.AsyncClient",
        client.factory,
    )

    with pytest.raises(ValueError, match="Extension API request failed"):
        await extension_client.send_extension_api_request(
            "caller",
            ["target"],
            "user-id",
            "access-token",
            ExtensionApiRequest(
                extension_id="target",
                method="GET",
                path="/api/v1/run",
                body=None,
            ),
        )


class _FakeAsyncClient:
    def __init__(self, response):
        self.response = response
        self.kwargs = {}
        self.stream_kwargs = {}

    def factory(self, **kwargs):
        self.kwargs = kwargs
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def stream(self, method, url, **kwargs):
        self.stream_kwargs = {"method": method, "url": url, **kwargs}
        return self.response


class _FakeStreamResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.encoding = "utf-8"
        self._chunks = chunks or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamError:
    async def __aenter__(self):
        raise httpx.RequestError(
            "network failed",
            request=httpx.Request("GET", "http://127.0.0.1"),
        )

    async def __aexit__(self, *_args):
        return False
