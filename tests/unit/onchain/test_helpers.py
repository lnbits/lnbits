import pytest

from lnbits.onchain.bindings import wally
from lnbits.onchain.helpers import (
    derive_address,
    descriptor_fingerprint,
    descriptor_type,
    parse_key,
)

from .test_psbt import VECTORS, signing_data


@pytest.mark.anyio
@pytest.mark.parametrize("vector", VECTORS["descriptors"])
async def test_existing_wallet_addresses_and_identity(vector):
    descriptor, network = parse_key(vector["text"])
    assert network["name"] == vector["network"]
    assert descriptor_fingerprint(descriptor) == vector["fingerprint"]
    assert descriptor_type(descriptor) == vector["type"]
    addresses = [
        await derive_address(vector["text"], i, b) for b in (0, 1) for i in (0, 3)
    ]
    assert addresses == vector["addresses"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "legacy,standard", [("{0,1}", "<0;1>"), ("{5,9}", "<5;9>"), ("{0}", "0")]
)
async def test_legacy_and_standard_branch_syntax_match(legacy, standard):
    _, text, _ = signing_data()
    standard = text.replace("{0,1}", standard)
    text = text.replace("{0,1}", legacy)
    for branch in (0, 1):
        assert await derive_address(text, 5, branch) == await derive_address(
            standard, 5, branch
        )


def test_rejects_mixed_networks():
    _, main, _ = signing_data(network="main")
    _, test, _ = signing_data(network="test")
    with pytest.raises(ValueError, match="different networks"):
        parse_key(f"wsh(sortedmulti(1,{main[5:-1]},{test[5:-1]}))")


def test_rejects_private_account_keys():
    root, _, _ = signing_data()
    private = wally.bip32_key_to_base58(root, wally.BIP32_FLAG_KEY_PRIVATE)
    for text in (private, f"wpkh({private}/0/*)"):
        with pytest.raises(ValueError, match="private key"):
            parse_key(text)


def test_rejects_non_account_bare_keys():
    root, _, _ = signing_data()
    with pytest.raises(ValueError, match="depth"):
        parse_key(wally.bip32_key_to_base58(root, wally.BIP32_FLAG_KEY_PUBLIC))


def test_rejects_descriptor_without_wildcard():
    _, text, _ = signing_data()
    with pytest.raises(ValueError, match="wildcards"):
        parse_key(text.replace("/{0,1}/*", "/0/0"))


@pytest.mark.anyio
async def test_fixed_branch_does_not_change_with_branch_index():
    _, text, _ = signing_data()
    text = text.replace("{0,1}", "0")
    assert await derive_address(text, 3, 0) == await derive_address(text, 3, 1)


@pytest.mark.anyio
@pytest.mark.parametrize("index,branch", [(-1, 0), (2**31, 0), (0, -1), (0, 2)])
async def test_rejects_invalid_derivation(index, branch):
    _, text, _ = signing_data()
    with pytest.raises(ValueError):
        await derive_address(text, index, branch)
