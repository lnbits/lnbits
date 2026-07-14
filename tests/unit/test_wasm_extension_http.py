import ipaddress
from typing import cast

import httpx
import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.wasm_ext.api.models import HttpRequest
from lnbits.core.wasm_ext.client import http as wasm_http


def test_wasm_http_origin_normalization_and_url_rejections():
    assert (
        wasm_http._request_origin("https://EXAMPLE.com/path") == "https://example.com"
    )
    assert (
        wasm_http._request_origin("https://example.com:8443/path")
        == "https://example.com:8443"
    )

    for url, message in [
        ("http://example.com", "https URLs"),
        ("https://user:pass@example.com", "credentials"),
        ("https:///missing-host", "hostname"),
        ("https://example.com:bad", "invalid port"),
    ]:
        with pytest.raises(PermissionError, match=message):
            wasm_http._request_origin(url)


@pytest.mark.anyio
async def test_wasm_http_rejects_internal_hosts(mocker: MockerFixture):
    with pytest.raises(PermissionError, match="localhost"):
        await wasm_http._reject_internal_host("https://localhost/api")

    with pytest.raises(PermissionError, match="internal network"):
        await wasm_http._reject_internal_host("https://127.0.0.1/api")

    mocker.patch(
        "lnbits.core.wasm_ext.client.http._resolve_host",
        mocker.AsyncMock(return_value=[ipaddress.ip_address("10.0.0.1")]),
    )
    with pytest.raises(PermissionError, match="internal network"):
        await wasm_http._reject_internal_host("https://api.example.com")


def test_wasm_http_strips_forbidden_headers_and_normalizes_timeout():
    assert wasm_http._request_headers(
        {
            " Host ": "evil.example",
            "Content-Length": "10",
            "X-Trace": "ok",
            "Cookie": "session=secret",
        }
    ) == {"X-Trace": "ok"}
    assert wasm_http._response_headers(
        {
            "content-length": "10",
            "set-cookie": "session=secret",
            "x-safe": "ok",
        }
    ) == {"x-safe": "ok"}
    assert wasm_http._timeout_seconds(None, 10.0) == 10.0
    assert wasm_http._timeout_seconds(2500, 10.0) == 2.5
    assert wasm_http._timeout_seconds(0, 10.0) is None


@pytest.mark.anyio
async def test_wasm_http_request_enforces_policies_and_response_bounds(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.wasm_ext.client.http._reject_internal_host",
        mocker.AsyncMock(),
    )
    client = _FakeAsyncClient(
        _FakeStreamResponse(
            status_code=201,
            headers={
                "content-type": "application/json",
                "set-cookie": "session=secret",
            },
            chunks=[b'{"ok":true}'],
        )
    )
    mocker.patch("lnbits.core.wasm_ext.client.http.httpx.AsyncClient", client.factory)

    response = await wasm_http.send_extension_http_request(
        "demoext",
        [{"host": "https://api.example.com"}],
        HttpRequest(
            method="POST",
            url="https://api.example.com/path",
            headers={"Host": "evil.example", "X-Test": "yes"},
            body="{}",
        ),
        timeout_ms=500,
        max_response_bytes=100,
    )

    assert response.status_code == 201
    assert response.body == '{"ok":true}'
    assert response.headers == {"content-type": "application/json"}
    assert client.kwargs["follow_redirects"] is False
    assert client.kwargs["trust_env"] is False
    assert client.kwargs["timeout"] == 0.5
    assert client.stream_kwargs["headers"] == {"X-Test": "yes"}

    with pytest.raises(PermissionError, match="not allowed"):
        await wasm_http.send_extension_http_request(
            "demoext",
            [{"host": "https://api.example.com"}],
            HttpRequest(url="https://other.example.com/path", body=None),
        )


@pytest.mark.anyio
async def test_wasm_http_request_rejects_oversized_bodies_and_responses(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.wasm_ext.client.http._reject_internal_host",
        mocker.AsyncMock(),
    )
    with pytest.raises(ValueError, match="body is too large"):
        await wasm_http.send_extension_http_request(
            "demoext",
            [{"host": "https://api.example.com"}],
            HttpRequest.construct(
                method="GET",
                url="https://api.example.com/path",
                headers={},
                body="x" * 65_537,
            ),
        )

    with pytest.raises(ValueError, match="response is too large"):
        await wasm_http._read_limited_response(
            cast(httpx.Response, _FakeStreamResponse(chunks=[b"12345", b"67890"])),
            max_response_bytes=8,
        )


@pytest.mark.anyio
async def test_wasm_http_request_hides_transport_errors(mocker: MockerFixture):
    mocker.patch(
        "lnbits.core.wasm_ext.client.http._reject_internal_host",
        mocker.AsyncMock(),
    )
    client = _FakeAsyncClient(_FakeStreamError())
    mocker.patch("lnbits.core.wasm_ext.client.http.httpx.AsyncClient", client.factory)

    with pytest.raises(ValueError, match="HTTP request failed"):
        await wasm_http.send_extension_http_request(
            "demoext",
            [{"host": "https://api.example.com"}],
            HttpRequest(url="https://api.example.com/path", body=None),
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
            request=httpx.Request("GET", "https://api.example.com"),
        )

    async def __aexit__(self, *_args):
        return False
