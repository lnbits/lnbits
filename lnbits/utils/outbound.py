"""Reject user-controlled requests back to the deployment itself."""

import asyncio
import errno
import ipaddress
import socket
from pathlib import Path

import httpx

from lnbits.settings import settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def instance_hostname() -> str:
    return (
        httpx.URL(settings.lnbits_baseurl).raw_host.decode("ascii").lower().rstrip(".")
    )


def check_outbound_hostname(host: str) -> None:
    hostname = httpx.URL(scheme="https", host=host).raw_host.decode("ascii")
    if hostname.lower().rstrip(".") == instance_hostname():
        raise ValueError("Requests to this server are not allowed.")


async def check_outbound_addresses(addresses: list[IPAddress]) -> None:
    # Check each request against current interfaces: do not cache stale addresses.
    # Binding a UDP socket sends no packets and works without enumerating interfaces
    # or adding a platform-specific dependency. Run OS operations off the event loop.
    await asyncio.to_thread(_check_addresses, addresses)


def outbound_protection_status() -> dict:
    container = Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()
    return {
        "hostname": instance_hostname(),
        "container_without_host_ips": container
        and not settings.lnbits_outbound_host_ips,
        "host_ip_count": len(settings.lnbits_outbound_host_ips),
    }


def _check_addresses(addresses: list[IPAddress]) -> None:
    supplied = {
        address
        for ip in settings.lnbits_outbound_host_ips
        for address in _embedded_addresses(ipaddress.ip_address(ip))
    }
    for address in addresses:
        for candidate in _embedded_addresses(address):
            if candidate in supplied or _is_assigned(candidate):
                raise ValueError("Requests to this server are not allowed.")


def _embedded_addresses(address: IPAddress) -> list[IPAddress]:
    result = [address]
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            result.append(address.ipv4_mapped)
        if address.sixtofour:
            result.append(address.sixtofour)
        if address.teredo:
            result.extend(address.teredo)
        if address in ipaddress.IPv6Network(
            "64:ff9b::/96"
        ) or address in ipaddress.IPv6Network("::/96"):
            result.append(ipaddress.IPv4Address(address.packed[-4:]))
    return result


def _is_assigned(address: IPAddress) -> bool:
    family = socket.AF_INET if address.version == 4 else socket.AF_INET6
    try:
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.bind((str(address), 0))
        return True
    except OSError as exc:
        if exc.errno in {errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT}:
            return False
        # Unexpected errors (e.g. exhausted descriptors) must not disable protection.
        raise ValueError("Cannot validate the outbound destination.") from exc
