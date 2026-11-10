import socket

import httpx
import pytest

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
@pytest.mark.parametrize(
    "target_ip",
    ["127.0.0.1", "10.0.0.2", "64:ff9b::127.0.0.1", "64:ff9b::a9fe:a9fe", "8.8.8.8"],
)
async def test_wasm_http_rejects_internal_and_self_hosts(
    safe_http_mock, settings, target_ip
):
    resolver, handler = safe_http_mock
    settings.lnbits_callback_allow_private_ips = True
    settings.lnbits_outbound_host_ips = ["8.8.8.8"]
    resolver.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (target_ip, 443))
    ]
    for url in (
        "https://api.example.com",
        str(httpx.URL("https://example.com").copy_with(host=target_ip)),
    ):
        with pytest.raises(PermissionError, match="target is not allowed"):
            await wasm_http.send_extension_http_request(
                "demoext", [url], HttpRequest(url=url, body=None)
            )
    handler.assert_not_called()


@pytest.mark.anyio
async def test_wasm_http_rejects_self_hostname_before_dns(safe_http_mock, settings):
    resolver, handler = safe_http_mock
    settings.lnbits_baseurl = "https://api.example.com"
    with pytest.raises(PermissionError, match="target is not allowed"):
        await wasm_http.send_extension_http_request(
            "demoext",
            ["https://api.example.com"],
            HttpRequest(url="https://api.example.com", body=None),
        )
    resolver.assert_not_awaited()
    handler.assert_not_called()


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
async def test_wasm_http_request_enforces_policies_and_pins_dns(
    safe_http_mock, settings
):
    resolver, handler = safe_http_mock
    settings.lnbits_callback_url_rules = [r"https://webhooks\.example"]

    def respond(request):
        # A later resolution would reach loopback, but the request is already pinned.
        resolver.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
        return httpx.Response(
            201,
            headers={
                "content-type": "application/json",
                "set-cookie": "session=secret",
            },
            content=b'{"ok":true}',
        )

    handler.side_effect = respond
    response = await wasm_http.send_extension_http_request(
        "demoext",
        [{"host": "https://api.example.com"}],
        HttpRequest(
            method="POST",
            url="https://api.example.com/path",
            headers={"Host": "evil.example", "Cookie": "secret", "X-Test": "yes"},
            body="{}",
        ),
        timeout_ms=500,
        max_response_bytes=100,
    )
    assert response.status_code == 201
    assert response.body == '{"ok":true}'
    assert response.headers == {"content-type": "application/json"}
    resolver.assert_awaited_once()
    request = handler.call_args.args[0]
    assert str(request.url) == "https://93.184.216.34/path"
    assert request.headers["host"] == "api.example.com"
    assert request.headers["x-test"] == "yes"
    assert "cookie" not in request.headers
    assert request.content == b"{}"
    assert request.extensions["sni_hostname"] == "api.example.com"
    assert request.extensions["timeout"]["read"] == 0.5

    with pytest.raises(PermissionError, match="not allowed"):
        await wasm_http.send_extension_http_request(
            "demoext",
            [{"host": "https://api.example.com"}],
            HttpRequest(url="https://other.example.com/path", body=None),
        )
    resolver.assert_awaited_once()
    handler.assert_called_once()


@pytest.mark.anyio
async def test_wasm_http_request_rejects_oversized_bodies_and_responses(safe_http_mock):
    resolver, handler = safe_http_mock
    with pytest.raises(ValueError, match="body is too large"):
        await wasm_http.send_extension_http_request(
            "demoext",
            [{"host": "https://api.example.com"}],
            HttpRequest.model_construct(
                method="GET",
                url="https://api.example.com/path",
                headers={},
                body="x" * 65_537,
            ),
        )
    resolver.assert_not_awaited()
    handler.assert_not_called()
    handler.side_effect = lambda request: httpx.Response(200, content=b"123456789")
    with pytest.raises(ValueError, match="response is too large"):
        await wasm_http.send_extension_http_request(
            "demoext",
            ["https://api.example.com"],
            HttpRequest(url="https://api.example.com", body=None),
            max_response_bytes=8,
        )
    handler.side_effect = lambda request: httpx.Response(
        200, content=b"x" * (wasm_http.HTTP_MAX_RESPONSE_BYTES + 1)
    )
    with pytest.raises(ValueError, match="response is too large"):
        await wasm_http.send_extension_http_request(
            "demoext",
            ["https://api.example.com"],
            HttpRequest(url="https://api.example.com", body=None),
        )


@pytest.mark.anyio
async def test_wasm_http_preserves_disabled_limits_and_does_not_follow_redirects(
    safe_http_mock,
):
    _, handler = safe_http_mock
    body = b"x" * 1048577
    handler.side_effect = lambda request: httpx.Response(200, content=body)
    response = await wasm_http.send_extension_http_request(
        "demoext",
        ["https://api.example.com"],
        HttpRequest(url="https://api.example.com", body=None),
        timeout_ms=0,
        max_response_bytes=0,
    )
    assert response.body == body.decode()
    assert handler.call_args.args[0].extensions["timeout"]["read"] is None
    handler.reset_mock()
    handler.side_effect = lambda request: httpx.Response(
        302, headers={"location": "https://other.example.com"}
    )
    response = await wasm_http.send_extension_http_request(
        "demoext",
        ["https://api.example.com"],
        HttpRequest(url="https://api.example.com", body=None),
    )
    assert response.status_code == 302
    handler.assert_called_once()


@pytest.mark.anyio
async def test_wasm_http_request_hides_transport_errors(safe_http_mock):
    _, handler = safe_http_mock
    handler.side_effect = httpx.ConnectError("sensitive transport detail")
    with pytest.raises(ValueError, match=r"^HTTP request failed\.$"):
        await wasm_http.send_extension_http_request(
            "demoext",
            [{"host": "https://api.example.com"}],
            HttpRequest(url="https://api.example.com/path", body=None),
        )
