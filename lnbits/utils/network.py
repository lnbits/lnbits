import ipaddress

_NAT64_NETWORK = ipaddress.IPv6Network("64:ff9b::/96")
_NAT64_LOCAL_NETWORK = ipaddress.IPv6Network("64:ff9b:1::/48")
_IPV4_COMPATIBLE_NETWORK = ipaddress.IPv6Network("::/96")


def is_global_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Require both the address and any embedded IPv4 addresses to be global."""
    if not address.is_global:
        return False
    if isinstance(address, ipaddress.IPv4Address):
        return True

    # Match newer Python versions; local NAT64 can use different IPv4 layouts.
    if address in _NAT64_LOCAL_NETWORK:
        return False
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_global
    if address.sixtofour is not None:
        return address.sixtofour.is_global
    if address.teredo is not None:
        return all(ip.is_global for ip in address.teredo)
    if address in _NAT64_NETWORK or address in _IPV4_COMPATIBLE_NETWORK:
        return ipaddress.IPv4Address(address.packed[-4:]).is_global
    return True
