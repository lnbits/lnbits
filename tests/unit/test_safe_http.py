import asyncio
import socket
from unittest.mock import AsyncMock

import httpx
import pytest

from lnbits.settings import settings
from lnbits.utils import safe_http


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def policy(monkeypatch):
    monkeypatch.setattr(settings, "lnbits_callback_url_rules", [])


def resolve(monkeypatch, addresses):
    dns = AsyncMock(
        return_value=[
            (
                socket.AF_INET6 if ":" in ip else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (ip, 443),
            )
            for ip in addresses
        ]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    return dns


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/server-key",
        "ftp://public.example/file",
        "gopher://public.example/",
        "https://user:secret@public.example/",
        "https://[fe80::1%25eth0]/",
    ],
)
async def test_unsafe_scheme_or_authority_never_connects(monkeypatch, url):
    dns = resolve(monkeypatch, ["93.184.216.34"])
    async with safe_http.SafeHttpClient() as client:
        send = AsyncMock()
        monkeypatch.setattr(client.client, "send", send)
        with pytest.raises((ValueError, httpx.InvalidURL)):
            await client.get(url)
        send.assert_not_awaited()
        dns.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.1.2",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",  # noqa: S104 - rejected destination, not a listening address
        "224.0.0.1",
        "::1",
        "::",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "64:ff9b::7f00:1",
        "64:ff9b:1::a00:1",
        "2002:7f00:1::",
        "2001:0:4136:e378:8000:63bf:3fff:fdd2",
    ],
)
async def test_nonpublic_and_embedded_addresses_never_connect(monkeypatch, ip):
    resolve(monkeypatch, [ip])
    async with safe_http.SafeHttpClient() as client:
        send = AsyncMock()
        monkeypatch.setattr(client.client, "send", send)
        with pytest.raises(ValueError):
            await client.get("https://public.example/")
        send.assert_not_awaited()


@pytest.mark.anyio
async def test_mixed_dns_answers_fail_closed(monkeypatch):
    resolve(monkeypatch, ["93.184.216.34", "127.0.0.1"])
    async with safe_http.SafeHttpClient() as client:
        send = AsyncMock()
        monkeypatch.setattr(client.client, "send", send)
        with pytest.raises(ValueError):
            await client.get("https://public.example/")
        send.assert_not_awaited()


@pytest.mark.anyio
async def test_pins_ip_preserves_host_tls_body_and_headers(monkeypatch):
    dns = resolve(monkeypatch, ["93.184.216.34"])
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    async with safe_http.SafeHttpClient() as client:
        client.client._transport = httpx.MockTransport(handler)
        result = await client.post(
            "https://public.example:8443/hook?token=abc",
            json={"amount": 7},
            headers={"Host": "localhost", "X-API-KEY": "secret"},
        )
    assert result.json() == {"ok": True}
    assert dns.await_count == 1
    assert seen[0].url.host == "93.184.216.34"
    assert seen[0].headers["host"] == "public.example:8443"
    assert seen[0].extensions["sni_hostname"] == "public.example"
    assert seen[0].headers["X-API-KEY"] == "secret"
    assert seen[0].content == b'{"amount": 7}'
    assert seen[0].url.query == b"token=abc"


@pytest.mark.anyio
async def test_redirect_revalidates_and_drops_credentials(monkeypatch):
    dns = resolve(monkeypatch, ["93.184.216.34"])
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(
                302,
                headers={
                    "location": "https://cdn.example/file",
                    "set-cookie": "key=secret",
                },
            )
        return httpx.Response(200, content=b"download")

    async with safe_http.SafeHttpClient(follow_redirects=True) as client:
        client.client._transport = httpx.MockTransport(handler)
        response = await client.get(
            "https://public.example/file",
            headers={
                "Authorization": "secret",
                "X-API-KEY": "secret",
                "Cookie": "secret",
            },
        )
    assert response.content == b"download"
    assert dns.await_count == 2
    assert seen[1].headers["host"] == "cdn.example"
    assert all(
        header not in seen[1].headers
        for header in ["authorization", "x-api-key", "cookie"]
    )


@pytest.mark.anyio
@pytest.mark.parametrize("target", ["file:///tmp/key", "https://internal.example/key"])
async def test_redirect_cannot_reach_files_or_private_dns(monkeypatch, target):
    dns = resolve(monkeypatch, ["93.184.216.34"])
    calls = []

    def handler(request):
        calls.append(request)
        dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
        return httpx.Response(302, headers={"location": target})

    async with safe_http.SafeHttpClient(follow_redirects=True) as client:
        client.client._transport = httpx.MockTransport(handler)
        with pytest.raises(ValueError):
            await client.get("https://public.example/")
    assert len(calls) == 1


@pytest.mark.anyio
async def test_webhooks_do_not_follow_redirects_or_read_response(monkeypatch):
    resolve(monkeypatch, ["93.184.216.34"])

    class UnreadableBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("Webhook response body must not be read")
            yield b""

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            302, headers={"location": "http://127.0.0.1/"}, stream=UnreadableBody()
        )

    async with safe_http.SafeHttpClient(read_body=False) as client:
        client.client._transport = httpx.MockTransport(handler)
        result = await client.post("https://public.example/hook", json={"paid": True})
    assert result.status_code == 302
    assert result.content == b""
    assert len(calls) == 1


@pytest.mark.anyio
async def test_response_size_and_redirect_count_are_bounded(monkeypatch):
    resolve(monkeypatch, ["93.184.216.34"])
    async with safe_http.SafeHttpClient() as client:
        client.client._transport = httpx.MockTransport(
            lambda r: httpx.Response(200, content=b"x" * 1048577)
        )
        with pytest.raises(ValueError, match="too large"):
            await client.get("https://public.example/")
    async with safe_http.SafeHttpClient(follow_redirects=True) as client:
        client.client._transport = httpx.MockTransport(
            lambda r: httpx.Response(302, headers={"location": "/again"})
        )
        with pytest.raises(ValueError, match="Too many"):
            await client.get("https://public.example/")


@pytest.mark.anyio
async def test_dns_failure_and_admin_rules_fail_closed(monkeypatch):
    dns = resolve(monkeypatch, [])
    with pytest.raises(ValueError):
        await safe_http.validate_url("https://public.example/")
    dns.side_effect = socket.gaierror()
    with pytest.raises(ValueError):
        await safe_http.validate_url("https://public.example/")
    dns.reset_mock()
    monkeypatch.setattr(
        settings, "lnbits_callback_url_rules", [r"https://allowed\.example"]
    )
    with pytest.raises(ValueError):
        await safe_http.validate_url("https://public.example/")
    dns.assert_not_awaited()


@pytest.mark.anyio
async def test_noncallback_requests_keep_destination_checks(monkeypatch):
    dns = resolve(monkeypatch, ["93.184.216.34"])
    monkeypatch.setattr(
        settings, "lnbits_callback_url_rules", [r"https://allowed\.example"]
    )
    async with safe_http.SafeHttpClient(apply_callback_rules=False) as client:
        client.client._transport = httpx.MockTransport(
            lambda request: httpx.Response(200)
        )
        assert (await client.get("https://public.example/")).status_code == 200
        dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
        with pytest.raises(safe_http.UnsafeHttpDestinationError):
            await client.get("https://public.example/")
        with pytest.raises(safe_http.UnsafeHttpDestinationError):
            await client.get("file:///tmp/key")


@pytest.mark.parametrize(
    "options",
    [{"follow_redirects": True}, {"private_endpoint": "http://mempool.example"}],
)
def test_private_callback_opt_in_cannot_enable_redirects_or_endpoint_exceptions(
    options,
):
    with pytest.raises(ValueError, match="Private callback access"):
        safe_http.SafeHttpClient(allow_private_ips=True, **options)


@pytest.mark.anyio
async def test_pinned_connection_falls_back_without_resolving_again(monkeypatch):
    dns = resolve(monkeypatch, ["93.184.216.34", "1.1.1.1"])
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("unreachable")
        return httpx.Response(200)

    async with safe_http.SafeHttpClient() as client:
        client.client._transport = httpx.MockTransport(handler)
        assert (await client.get("https://public.example/")).status_code == 200
    dns.assert_awaited_once()
    assert [request.url.host for request in calls] == ["93.184.216.34", "1.1.1.1"]
    assert all(request.headers["host"] == "public.example" for request in calls)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.2.3.4", "172.20.0.2", "192.168.1.2", "::1", "fd00::1"]
)
async def test_private_endpoint_opt_in_is_scoped_and_pinned(monkeypatch, address):
    resolve(monkeypatch, [address])
    async with safe_http.SafeHttpClient(
        private_endpoint="http://mempool.example:3006/testnet"
    ) as client:
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=[])

        client.client._transport = httpx.MockTransport(handler)
        result = await client.get(
            "http://mempool.example:3006/testnet/api/address/address/txs"
        )
        assert result.json() == []
        assert requests[0].url.host == address
        assert requests[0].headers["host"] == "mempool.example:3006"
        for url in [
            "http://other.example:3006/testnet/api",
            "http://mempool.example:3007/testnet/api",
            "http://mempool.example:3006/admin",
            "http://mempool.example:3006/testnet/%2e%2e/admin",
            r"http://mempool.example:3006/testnet/..\admin",
        ]:
            with pytest.raises(ValueError):
                await client.get(url)
        assert len(requests) == 1
    with pytest.raises(ValueError):
        await safe_http.validate_url("http://mempool.example:3006/testnet/api")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",
        "169.254.170.2",
        "fd00:ec2::254",
        "0.0.0.0",  # noqa: S104 - rejected destination, not a listening address
        "224.0.0.1",
        "::",
        "fe80::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "64:ff9b::7f00:1",
        "100.100.100.200",
    ],
)
async def test_private_opt_in_never_allows_metadata_or_special_addresses(
    monkeypatch, address
):
    resolve(monkeypatch, [address])
    with pytest.raises(ValueError):
        await safe_http.validate_url(
            "http://mempool.example/api", private_endpoint="http://mempool.example"
        )


@pytest.mark.anyio
async def test_private_opt_in_keeps_public_self_and_mixed_dns_blocked(monkeypatch):
    monkeypatch.setattr(settings, "lnbits_outbound_host_ips", ["8.8.8.8"])
    resolve(monkeypatch, ["8.8.8.8"])
    with pytest.raises(ValueError, match="this server"):
        await safe_http.validate_url(
            "https://alias.example/api", private_endpoint="https://alias.example"
        )
    resolve(monkeypatch, ["8.8.8.8", "10.0.0.2"])
    with pytest.raises(ValueError):
        await safe_http.validate_url(
            "https://alias.example/api", private_endpoint="https://alias.example"
        )
    monkeypatch.setattr(settings, "lnbits_baseurl", "http://mempool.example:3006/")
    resolve(monkeypatch, ["127.0.0.1"])
    with pytest.raises(ValueError, match="this server"):
        await safe_http.validate_url(
            "http://mempool.example:3006/api",
            private_endpoint="http://mempool.example:3006",
        )


def test_private_endpoint_cannot_enable_redirects():
    with pytest.raises(ValueError, match="redirects"):
        safe_http.SafeHttpClient(
            private_endpoint="http://mempool.example", follow_redirects=True
        )


@pytest.mark.anyio
async def test_websocket_pins_ip_preserving_origin_and_disables_proxy(monkeypatch):
    from unittest.mock import Mock

    resolve(monkeypatch, ["93.184.216.34"])
    connection = AsyncMock()
    factory = Mock(return_value=connection)
    monkeypatch.setattr(safe_http, "_NoRedirectConnect", factory)
    async with safe_http.safe_websocket("wss://mempool.example/api/v1/ws") as websocket:
        assert websocket is connection.__aenter__.return_value
    args, kwargs = factory.call_args
    assert args == ("wss://mempool.example/api/v1/ws",)
    assert kwargs["host"] == "93.184.216.34"
    assert kwargs["port"] == 443 and kwargs["proxy"] is None
    connection.__aexit__.assert_awaited_once()


@pytest.mark.anyio
async def test_websocket_rejects_private_without_opt_in(monkeypatch):
    from unittest.mock import Mock

    resolve(monkeypatch, ["127.0.0.1"])
    factory = Mock(return_value=AsyncMock())
    monkeypatch.setattr(safe_http, "_NoRedirectConnect", factory)
    with pytest.raises(ValueError):
        async with safe_http.safe_websocket("ws://mempool.example:3006/api/v1/ws"):
            pytest.fail("connected")
    factory.assert_not_called()
    async with safe_http.safe_websocket(
        "ws://mempool.example:3006/api/v1/ws",
        private_endpoint="http://mempool.example:3006",
    ):
        pass
    assert factory.call_args.kwargs["host"] == "127.0.0.1"


def test_websocket_redirect_is_never_followed():
    from websockets.datastructures import Headers
    from websockets.exceptions import InvalidStatus
    from websockets.http11 import Response

    connection = safe_http._NoRedirectConnect(
        "wss://mempool.example/api/v1/ws", proxy=None
    )
    for location in ["/admin", "ws://169.254.169.254/", "wss://other.example/"]:
        error = InvalidStatus(Response(302, "Found", Headers({"Location": location})))
        assert connection.process_redirect(error) is error
