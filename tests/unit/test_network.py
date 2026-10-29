import ipaddress

import pytest

from lnbits.utils.network import is_global_address


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "64:ff9b::127.0.0.1",
        "64:ff9b::10.0.0.1",
        "64:ff9b::a9fe:a9fe",
        "64:ff9b::100.64.0.1",
        "64:ff9b::240.0.0.1",
        "64:ff9b:1::127.0.0.1",
        "64:ff9b:1::8.8.8.8",
        "2002:7f00:0001::",
        "2002:c0a8:0101::",
        "2001:0:808:808:0:0:80ff:fffe",
        "::ffff:127.0.0.1",
        "::ffff:100.64.0.1",
        "::127.0.0.1",
    ],
)
def test_is_global_address_rejects_internal_targets(address: str):
    assert not is_global_address(ipaddress.ip_address(address))


@pytest.mark.parametrize(
    "address",
    [
        "8.8.8.8",
        "2606:4700:4700::1111",
        "2606:4700::7f00:1",
        "64:ff9b::8.8.8.8",
        "::ffff:8.8.8.8",
        "::8.8.8.8",
    ],
)
def test_is_global_address_allows_public_targets(address: str):
    assert is_global_address(ipaddress.ip_address(address))
