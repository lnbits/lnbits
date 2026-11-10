"""Restricted HTTP transport for user-controlled destinations.

Core and extensions use this client for arbitrary URLs supplied by users. By
default it requires public destinations and applies administrator callback rules.
Non-callback protocols can disable those rules while retaining destination checks.
Trusted internal integrations have separate connection requirements. An explicit
private_endpoint supplied by trusted administrator configuration permits LAN/ULA
and loopback destinations only within that origin/path; public self-addresses,
metadata addresses and redirects remain blocked.

Core webhooks may explicitly retain the administrator's legacy private-IP opt-in
with allow_private_ips. This does not bypass callback rules or self-target checks.
"""

import asyncio
import ipaddress
import socket
from contextlib import asynccontextmanager

import httpx
from websockets.asyncio.client import connect

from lnbits.helpers import check_callback_url
from lnbits.settings import settings
from lnbits.utils.outbound import check_outbound_addresses, check_outbound_hostname


class UnsafeHttpDestinationError(ValueError):
    """The request destination failed validation before connecting."""


class SafeHttpClient:
    def __init__(
        self,
        *,
        timeout: float | httpx.Timeout | None = 10,
        follow_redirects=False,
        read_body=True,
        private_endpoint=None,
        apply_callback_rules: bool = True,
        allow_private_ips: bool = False,
    ):
        # Only trusted administrator configuration may provide this exception.
        # It is confined to one origin/path and never permits redirects.
        if private_endpoint is not None and follow_redirects:
            raise ValueError("Private endpoint redirects are not allowed.")
        if allow_private_ips and (follow_redirects or private_endpoint is not None):
            raise ValueError(
                "Private callback access cannot use redirects or endpoints."
            )
        self.private_endpoint = private_endpoint
        self.follow_redirects = follow_redirects
        self.read_body = read_body
        self.apply_callback_rules = apply_callback_rules
        self.allow_private_ips = allow_private_ips
        self.client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, trust_env=False
        )

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.client.__aexit__(*args)

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.request("DELETE", url, **kwargs)

    async def request(self, method, url, **kwargs):
        async with self.stream(method, url, **kwargs) as response:
            body = bytearray()
            if self.read_body:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    body.extend(chunk)
                    if len(body) > 1048576:
                        raise ValueError("HTTP response is too large.")
            # The streaming response is closed here; return a buffered response.
            headers = response.headers.copy()
            headers.pop("content-encoding", None)
            headers.pop("content-length", None)
            return httpx.Response(
                response.status_code,
                headers=headers,
                content=bytes(body),
                request=response.request,
            )

    @asynccontextmanager
    async def stream(self, method, url, **kwargs):
        request = self.client.build_request(method, url, **kwargs)
        for redirect in range(4):
            try:
                addresses = await validate_url(
                    request.url,
                    private_endpoint=self.private_endpoint,
                    apply_callback_rules=self.apply_callback_rules,
                    allow_private_ips=self.allow_private_ips,
                )
            except (ValueError, httpx.InvalidURL) as exc:
                raise UnsafeHttpDestinationError(str(exc)) from exc
            response = await self._send(request, addresses)
            try:
                if not self.follow_redirects or not response.has_redirect_location:
                    yield response
                    return
                if redirect == 3:
                    raise ValueError("Too many HTTP redirects.")
                # Only read-only downloads follow redirects. Never replay payments
                # or webhook credentials/bodies to a destination chosen by a server.
                if request.method not in {"GET", "HEAD"}:
                    raise ValueError("Redirect for this HTTP method is not allowed.")
                target = request.url.join(response.headers["location"])
                if request.url.scheme == "https" and target.scheme != "https":
                    raise ValueError("HTTPS downgrade is not allowed.")
                headers = request.headers.copy()
                if _origin(target) != _origin(request.url):
                    headers = httpx.Headers()
                headers.pop("host", None)
                # Do not carry cookies collected by the underlying client.
                request = httpx.Request(request.method, target, headers=headers)
            finally:
                await response.aclose()
        raise ValueError("HTTP request could not be completed.")

    async def _send(self, request, addresses):
        for index, address in enumerate(addresses):
            pinned = httpx.Request(
                request.method,
                request.url.copy_with(host=address),
                headers=request.headers,
                content=request.content,
                extensions={**request.extensions, "sni_hostname": request.url.host},
            )
            # Use the validated URL's hostname for HTTP routing and TLS verification.
            pinned.headers["Host"] = request.url.netloc.decode("ascii")
            # An IP-keyed pool must not reuse TLS verified for a different host.
            pinned.headers["Connection"] = "close"
            try:
                return await self.client.send(pinned, stream=True)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if index == len(addresses) - 1:
                    raise
        raise ValueError("HTTP target could not be resolved.")


async def validate_url(
    value, *, private_endpoint=None, apply_callback_rules=True, allow_private_ips=False
) -> list[str]:
    url = httpx.URL(value)
    _check_http_url(url)
    # Other protocols (e.g. WASM HTTP) enforce their own origin permissions.
    if apply_callback_rules:
        check_callback_url(str(url))
    if private_endpoint is None:
        check_outbound_hostname(url.host)
    else:
        _check_endpoint_scope(url, httpx.URL(private_endpoint))
    try:
        infos = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(
                url.host,
                url.port or (443 if url.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            ),
            timeout=5,
        )
        addresses = list(dict.fromkeys(ipaddress.ip_address(i[4][0]) for i in infos))
    except (OSError, ValueError, asyncio.TimeoutError) as exc:
        raise ValueError("HTTP target could not be resolved.") from exc
    await _check_addresses(
        url,
        addresses,
        private_endpoint=private_endpoint,
        allow_private_ips=allow_private_ips,
    )
    return [str(address) for address in addresses]


@asynccontextmanager
async def safe_websocket(url, *, private_endpoint=None, apply_callback_rules=True):
    """Connect to a validated, pinned WebSocket target without redirects or proxies."""
    target = httpx.URL(url)
    if target.scheme not in {"ws", "wss"}:
        raise ValueError("WebSocket target is not allowed.")
    http_url = target.copy_with(scheme="https" if target.scheme == "wss" else "http")
    addresses = await validate_url(
        http_url,
        private_endpoint=private_endpoint,
        apply_callback_rules=apply_callback_rules,
    )
    for index, address in enumerate(addresses):
        connected = False
        try:
            async with _NoRedirectConnect(
                str(target),
                host=address,
                port=target.port or (443 if target.scheme == "wss" else 80),
                proxy=None,
                open_timeout=5,
                close_timeout=1,
                max_size=1048576,
            ) as websocket:
                connected = True
                yield websocket
                return
        except (OSError, asyncio.TimeoutError):
            if connected or index == len(addresses) - 1:
                raise


class _NoRedirectConnect(connect):
    def process_redirect(self, exc):
        return exc


def _check_http_url(url):
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.userinfo
        or "%" in url.host
    ):
        raise ValueError("HTTP target is not allowed.")


def _check_endpoint_scope(url, endpoint):
    _check_http_url(endpoint)
    if (
        endpoint.query
        or endpoint.fragment
        or _origin(url) != _origin(endpoint)
        or not (
            url.path == endpoint.path
            or url.path.startswith(endpoint.path.rstrip("/") + "/")
        )
        or b"%" in url.raw_path.split(b"?", 1)[0]
        or "\\" in url.path
        or "\\" in endpoint.path
    ):
        raise ValueError("Request is outside the configured private endpoint.")


async def _check_addresses(
    url, addresses, *, private_endpoint, allow_private_ips=False
):
    if (
        addresses
        and private_endpoint is not None
        and all(_is_private_service_address(address) for address in addresses)
    ):
        if _origin(url) == _origin(httpx.URL(settings.lnbits_baseurl)):
            raise ValueError("Requests to this server are not allowed.")
        return
    if not addresses or (
        not allow_private_ips and any(not _is_public(address) for address in addresses)
    ):
        raise ValueError("HTTP target must resolve only to public addresses.")
    check_outbound_hostname(url.host)
    await check_outbound_addresses(addresses)


def _is_private_service_address(address):
    # Explicit private services may use LAN/ULA or loopback addresses, never
    # cloud metadata/link-local, multicast, unspecified or transition addresses.
    # EC2's IPv6 metadata endpoint is ULA rather than link-local.
    if address == ipaddress.ip_address("fd00:ec2::254"):
        return False
    networks = (
        ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")
        if address.version == 4
        else ("fc00::/7", "::1/128")
    )
    return any(address in ipaddress.ip_network(network) for network in networks)


def _origin(url):
    return url.scheme, url.host, url.port


def _is_public(address):
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if isinstance(address, ipaddress.IPv4Address):
        return True
    if address.ipv4_mapped:
        return _is_public(address.ipv4_mapped)
    if address.sixtofour:
        return _is_public(address.sixtofour)
    if address.teredo:
        return all(_is_public(ip) for ip in address.teredo)
    if address in ipaddress.IPv6Network("64:ff9b:1::/48"):
        return False
    if address in ipaddress.IPv6Network("64:ff9b::/96"):
        return _is_public(ipaddress.IPv4Address(address.packed[-4:]))
    return True
