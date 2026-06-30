from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from .models import HttpRequest, HttpResponse

HTTP_REQUEST_TIMEOUT_SECONDS = 5.0
HTTP_MAX_RESPONSE_BYTES = 262_144

_FORBIDDEN_REQUEST_HEADERS = {
    "connection",
    "content-length",
    "cookie",
    "host",
    "proxy-authorization",
    "transfer-encoding",
}
_FORBIDDEN_RESPONSE_HEADERS = {
    "connection",
    "content-length",
    "set-cookie",
    "transfer-encoding",
}


async def send_extension_http_request(
    extension_id: str,
    policy: dict[str, Any],
    request: HttpRequest,
) -> HttpResponse:
    allowed_origins = _allowed_origins(policy)
    origin = _request_origin(request.url)
    if origin not in allowed_origins:
        raise PermissionError(
            f"Extension '{extension_id}' is not allowed to request '{origin}'."
        )

    await _reject_internal_host(request.url)
    headers = _request_headers(request.headers)
    body = request.body.encode() if request.body is not None else b""
    if len(body) > 65_536:
        raise ValueError("HTTP request body is too large.")

    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client:
            async with client.stream(
                request.method,
                request.url,
                headers=headers,
                content=body,
            ) as response:
                response_body = await _read_limited_response(response)
                return HttpResponse(
                    status_code=response.status_code,
                    headers=_response_headers(dict(response.headers)),
                    body=response_body.decode(response.encoding or "utf-8", "replace"),
                )
    except httpx.RequestError as exc:
        raise ValueError("HTTP request failed.") from exc


def _allowed_origins(policy: dict[str, Any]) -> set[str]:
    hosts = policy.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        raise PermissionError("HTTP requests require a non-empty hosts policy.")

    origins: set[str] = set()
    for host in hosts:
        if not isinstance(host, str) or not host:
            continue
        origins.add(_request_origin(host))
    if not origins:
        raise PermissionError("HTTP requests require at least one valid host.")
    return origins


def _request_origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise PermissionError("HTTP requests require https URLs.")
    if parsed.username or parsed.password:
        raise PermissionError("HTTP requests cannot include credentials in URLs.")
    if not parsed.hostname:
        raise PermissionError("HTTP requests require a hostname.")

    hostname = parsed.hostname.lower()
    port = _url_port(parsed)
    if port is None or port == 443:
        return f"https://{hostname}"
    return f"https://{hostname}:{port}"


def _url_port(parsed: Any) -> int | None:
    try:
        return parsed.port
    except ValueError as exc:
        raise PermissionError("HTTP request URL has an invalid port.") from exc


async def _reject_internal_host(url: str) -> None:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise PermissionError("HTTP requests require a hostname.")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise PermissionError("HTTP requests cannot target localhost.")

    try:
        address = ipaddress.ip_address(hostname)
        _reject_internal_address(address)
        return
    except ValueError:
        pass

    for address in await _resolve_host(hostname):
        _reject_internal_address(address)


async def _resolve_host(
    hostname: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    import asyncio

    def resolve() -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        try:
            infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise PermissionError("HTTP request host could not be resolved.") from exc

        addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for info in infos:
            sockaddr = info[4]
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        return addresses

    return await asyncio.to_thread(resolve)


def _reject_internal_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> None:
    if not address.is_global:
        raise PermissionError("HTTP requests cannot target internal network addresses.")


def _request_headers(headers: dict[str, str]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in headers.items():
        header = key.strip()
        if not header:
            continue
        if header.lower() in _FORBIDDEN_REQUEST_HEADERS:
            continue
        clean[header] = value
    return clean


async def _read_limited_response(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > HTTP_MAX_RESPONSE_BYTES:
            raise ValueError("HTTP response is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def _response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _FORBIDDEN_RESPONSE_HEADERS
    }
