import re
from dataclasses import dataclass
from typing import Any

from starlette.concurrency import run_in_threadpool

from .bindings import wally

# SLIP132 prefixes encode both the network and the policy of a bare account key.
_PUBLIC_VERSIONS = {
    "0488b21e": (wally.WALLY_NETWORK_BITCOIN_MAINNET, "pkh"),
    "049d7cb2": (wally.WALLY_NETWORK_BITCOIN_MAINNET, "sh"),
    "04b24746": (wally.WALLY_NETWORK_BITCOIN_MAINNET, "wpkh"),
    "0295b43f": (wally.WALLY_NETWORK_BITCOIN_MAINNET, None),
    "02aa7ed3": (wally.WALLY_NETWORK_BITCOIN_MAINNET, None),
    "043587cf": (wally.WALLY_NETWORK_BITCOIN_TESTNET, "pkh"),
    "044a5262": (wally.WALLY_NETWORK_BITCOIN_TESTNET, "sh"),
    "045f1cf6": (wally.WALLY_NETWORK_BITCOIN_TESTNET, "wpkh"),
    "024289ef": (wally.WALLY_NETWORK_BITCOIN_TESTNET, None),
    "02575483": (wally.WALLY_NETWORK_BITCOIN_TESTNET, None),
}
_NETWORK_NAMES = {
    wally.WALLY_NETWORK_BITCOIN_MAINNET: "Mainnet",
    wally.WALLY_NETWORK_BITCOIN_TESTNET: "Testnet",
}
_KEY = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{100,120}\b")
_BRANCH = re.compile(r"/\{(\d+(?:,\d+)*)\}")
_SCRIPT_TYPES = {
    wally.WALLY_SCRIPT_TYPE_P2PKH: "p2pkh",
    wally.WALLY_SCRIPT_TYPE_P2SH: "p2sh",
    wally.WALLY_SCRIPT_TYPE_P2WPKH: "p2wpkh",
    wally.WALLY_SCRIPT_TYPE_P2WSH: "p2wsh",
    wally.WALLY_SCRIPT_TYPE_P2TR: "p2tr",
}


@dataclass
class TaprootDescriptor:
    """Wally parses Tapscript leaves separately from key-only tr() descriptors."""

    internal_key: Any
    tree: Any
    leaves: list[Any]


def _native_descriptor(descriptor: Any) -> Any:
    return (
        descriptor.internal_key
        if isinstance(descriptor, TaprootDescriptor)
        else descriptor
    )


def _parse_taproot_tree(
    expression: str, network: int, leaves: list[Any], depth: int = 0
) -> Any:
    if depth > 128:
        raise ValueError("Taproot tree is too deep")
    if expression.startswith("{"):
        if not expression.endswith("}"):
            raise ValueError("Invalid Taproot tree")
        inner = expression[1:-1]
        nesting = 0
        for index, char in enumerate(inner):
            if char in "({":
                nesting += 1
            elif char in ")}":
                nesting -= 1
            elif char == "," and nesting == 0:
                return (
                    _parse_taproot_tree(inner[:index], network, leaves, depth + 1),
                    _parse_taproot_tree(inner[index + 1 :], network, leaves, depth + 1),
                )
        raise ValueError("Invalid Taproot tree")
    leaf = wally.descriptor_parse(
        expression,
        None,
        network,
        wally.WALLY_MINISCRIPT_ONLY | wally.WALLY_MINISCRIPT_TAPSCRIPT,
    )
    leaves.append(leaf)
    return leaf


def parse_key(masterpub: str) -> tuple[Any, dict]:  # noqa: C901
    """Read existing account keys/descriptors without changing their stored text."""
    # As before, the optional checksum is not part of the parsed expression.
    # Legacy path syntax and SLIP132 prefixes change its serialized checksum.
    expression = masterpub.split("#", 1)[0]
    bare = "(" not in expression
    networks = set()
    policy = None

    def normalize_key(match: re.Match) -> str:
        nonlocal policy
        raw = bytes(wally.base58_to_bytes(match[0], wally.BASE58_FLAG_CHECKSUM))
        if len(raw) != 78 or raw[:4].hex() not in _PUBLIC_VERSIONS:
            raise ValueError("Unknown master public key version or private key")
        network, policy = _PUBLIC_VERSIONS[raw[:4].hex()]
        networks.add(network)
        if bare and raw[4] != 3:
            raise ValueError(
                "Non-standard depth. Only bip44, bip49 and bip84 are supported "
                "with bare xpubs. For custom derivation paths use descriptors."
            )
        version = (
            wally.BIP32_VER_MAIN_PUBLIC
            if network == wally.WALLY_NETWORK_BITCOIN_MAINNET
            else wally.BIP32_VER_TEST_PUBLIC
        )
        return wally.base58_from_bytes(
            version.to_bytes(4, "big") + raw[4:], wally.BASE58_FLAG_CHECKSUM
        )

    expression = _KEY.sub(normalize_key, expression)
    if len(networks) > 1:
        raise ValueError("Keys from different networks")
    expression = _BRANCH.sub(
        lambda m: "/<" + m[1].replace(",", ";") + ">" if "," in m[1] else "/" + m[1],
        expression,
    )
    if bare:
        if policy is None:
            raise ValueError("The key is not a supported master public key")
        match = _KEY.search(expression)
        if match and match.end() == len(expression):
            expression += "/<0;1>/*"
        expression = (
            f"sh(wpkh({expression}))" if policy == "sh" else f"{policy}({expression})"
        )
    network = next(iter(networks), wally.WALLY_NETWORK_NONE)
    descriptors: list[Any] = []
    if expression.startswith("tr(") and "," in expression:
        key, tree_text = expression[3:-1].split(",", 1)
        internal_key = wally.descriptor_parse(f"tr({key})", None, network, 0)
        tree = _parse_taproot_tree(tree_text, network, descriptors)
        descriptor = TaprootDescriptor(internal_key, tree, descriptors.copy())
        descriptors.append(internal_key)
    else:
        descriptor = wally.descriptor_parse(expression, None, network, 0)
        descriptors.append(descriptor)
    features = 0
    for native in descriptors:
        features |= wally.descriptor_get_features(native)
    paths = {wally.descriptor_get_num_paths(d) for d in descriptors} - {0, 1}
    if len(paths) > 1:
        raise ValueError("Descriptor keys have different numbers of branches")
    if features & wally.WALLY_MS_IS_PRIVATE:
        raise ValueError("Private keys are not allowed")
    if not features & wally.WALLY_MS_IS_RANGED:
        raise ValueError("Descriptor should have wildcards")
    network = wally.descriptor_get_network(_native_descriptor(descriptor))
    if network not in _NETWORK_NAMES:
        raise ValueError("Unknown master public key network")
    return descriptor, {"name": _NETWORK_NAMES[network]}


def descriptor_fingerprint(descriptor: Any) -> str:
    descriptor = _native_descriptor(descriptor)
    if wally.descriptor_get_key_features(descriptor, 0) & wally.WALLY_MS_IS_PARENTED:
        return bytes(wally.descriptor_get_key_origin_fingerprint(descriptor, 0)).hex()
    key = wally.bip32_key_from_base58(wally.descriptor_get_key(descriptor, 0))
    return bytes(wally.bip32_key_get_fingerprint(key)).hex()


def descriptor_branch(descriptor: Any, branch_index: int) -> int:
    descriptors = (
        [descriptor.internal_key, *descriptor.leaves]
        if isinstance(descriptor, TaprootDescriptor)
        else [descriptor]
    )
    paths = max(wally.descriptor_get_num_paths(d) for d in descriptors)
    if branch_index < 0 or (paths > 1 and branch_index >= paths):
        raise ValueError("Invalid descriptor branch")
    return branch_index if paths > 1 else 0


def descriptor_script(
    descriptor: Any, address_index: int = 0, branch_index: int = 0, depth: int = 0
) -> bytes:
    if not 0 <= address_index < 2**31:
        raise ValueError("Invalid address index")
    if isinstance(descriptor, TaprootDescriptor):
        if depth:
            raise ValueError("Taproot script-path signing is not supported")
        branch = descriptor_branch(descriptor, branch_index)
        merkle_root = _taproot_hash(descriptor.tree, address_index, branch)
        key = descriptor_script(descriptor.internal_key, address_index, branch, 1)
        if len(key) == 32:
            key = b"\x02" + key
        tweaked = bytes(wally.ec_public_key_bip341_tweak(key, merkle_root, 0))
        return b"\x51\x20" + tweaked[1:]
    child = (
        address_index
        if wally.descriptor_get_features(descriptor) & wally.WALLY_MS_IS_RANGED
        else 0
    )
    return bytes(
        wally.descriptor_to_script(
            descriptor,
            depth,
            0,
            0,
            descriptor_branch(descriptor, branch_index),
            child,
            0,
        )
    )


def _taproot_hash(tree: Any, address_index: int, branch_index: int) -> bytes:
    if isinstance(tree, tuple):
        children = sorted(_taproot_hash(t, address_index, branch_index) for t in tree)
        return bytes(wally.bip340_tagged_hash(b"".join(children), "TapBranch"))
    script = descriptor_script(tree, address_index, branch_index)
    serialized = b"\xc0" + bytes(wally.varint_to_bytes(len(script))) + script
    return bytes(wally.bip340_tagged_hash(serialized, "TapLeaf"))


def descriptor_type(descriptor: Any) -> str:
    return _SCRIPT_TYPES[wally.scriptpubkey_get_type(descriptor_script(descriptor))]


async def derive_address(masterpub: str, num: int, branch_index: int = 0) -> str:
    return await run_in_threadpool(_derive_address, masterpub, num, branch_index)


def _derive_address(masterpub: str, num: int, branch_index: int) -> str:
    descriptor, _ = parse_key(masterpub)
    return script_address(
        descriptor_script(descriptor, num, branch_index),
        wally.descriptor_get_network(_native_descriptor(descriptor)),
    )


def address_script(address: str) -> bytes:
    family = address.lower().split("1", 1)[0]
    if family in ("bc", "tb", "bcrt"):
        return bytes(wally.addr_segwit_to_bytes(address, family, 0))
    for network in _NETWORK_NAMES:
        try:
            return bytes(wally.address_to_scriptpubkey(address, network))
        except ValueError:
            continue
    raise ValueError("Invalid Bitcoin address")


def script_address(script: bytes, network: int) -> str:
    if wally.scriptpubkey_get_type(script) in (
        wally.WALLY_SCRIPT_TYPE_P2WPKH,
        wally.WALLY_SCRIPT_TYPE_P2WSH,
        wally.WALLY_SCRIPT_TYPE_P2TR,
    ):
        family = "bc" if network == wally.WALLY_NETWORK_BITCOIN_MAINNET else "tb"
        return wally.addr_segwit_from_bytes(script, family, 0)
    return wally.scriptpubkey_to_address(script, network)


def transaction_details(transaction: Any, network: int) -> dict:
    return {
        "locktime": wally.tx_get_locktime(transaction),
        "version": wally.tx_get_version(transaction),
        "outputs": [
            {
                "amount": wally.tx_get_output_satoshi(transaction, index),
                "address": script_address(
                    bytes(wally.tx_get_output_script(transaction, index)), network
                ),
            }
            for index in range(wally.tx_get_num_outputs(transaction))
        ],
    }
