"""Restricted HTTP transport for user-controlled destinations.

Extensions should use this client for arbitrary URLs supplied by users. It
requires public destinations and applies the administrator callback URL rules.
Trusted internal integrations have separate connection requirements.
"""

import asyncio
import ipaddress
import socket
from contextlib import asynccontextmanager

import httpx

from lnbits.helpers import check_callback_url
from lnbits.utils.outbound import check_outbound_addresses, check_outbound_hostname


class SafeHttpClient:
    def __init__(self, *, timeout=10, follow_redirects=False, read_body=True):
        self.follow_redirects = follow_redirects
        self.read_body = read_body
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
            addresses = await validate_url(request.url)
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


async def validate_url(value) -> list[str]:
    url = httpx.URL(value)
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.userinfo
        or "%" in url.host
    ):
        raise ValueError("HTTP target is not allowed.")
    check_callback_url(str(url))
    check_outbound_hostname(url.host)
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
    if not addresses or any(not _is_public(address) for address in addresses):
        raise ValueError("HTTP target must resolve only to public addresses.")
    await check_outbound_addresses(addresses)
    return [str(address) for address in addresses]


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
