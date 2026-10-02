"""Bitcoin key, descriptor, address, and PSBT utilities."""

import base64
import re
import secrets
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import wallycore  # type: ignore[import-untyped]
from Cryptodome.Cipher import AES
from starlette.concurrency import run_in_threadpool

from lnbits.core.models.onchain import CreatePsbt

# Native calls return allocated Python bytes; the SWIG source signatures are not
# their runtime signatures. Deterministic descriptor/signing vectors cover them.
wally: Any = wallycore

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


def new_mnemonic(supplied: str | None = None) -> str:
    words = wally.bip39_get_wordlist("en")
    if supplied is not None:
        mnemonic = " ".join(supplied.split()).lower()
        wally.bip39_mnemonic_validate(words, mnemonic)
        return mnemonic
    return wally.bip39_mnemonic_from_bytes(words, secrets.token_bytes(32))


def root_key(mnemonic: str, network: str):
    return wally.bip32_key_from_seed(
        wally.bip39_mnemonic_to_seed512(mnemonic, ""),
        (
            wally.BIP32_VER_MAIN_PRIVATE
            if network == "Mainnet"
            else wally.BIP32_VER_TEST_PRIVATE
        ),
        wally.BIP32_FLAG_KEY_PRIVATE,
    )


def wallet_descriptor(
    mnemonic: str,
    network: str,
    script_type: str = "p2wpkh",
    account_path: str | None = None,
) -> tuple[str, str]:
    root = root_key(mnemonic, network)
    coin = 0 if network == "Mainnet" else 1
    purpose, template = {
        "p2pkh": (44, "pkh({key})"),
        "p2sh": (49, "sh(wpkh({key}))"),
        "p2wpkh": (84, "wpkh({key})"),
        "p2tr": (86, "tr({key})"),
    }[script_type]
    path = (account_path or f"m/{purpose}'/{coin}'/0'")[2:]
    account = wally.bip32_key_from_parent_path(
        root, _path(path), wally.BIP32_FLAG_KEY_PRIVATE
    )
    xpub = wally.bip32_key_to_base58(account, wally.BIP32_FLAG_KEY_PUBLIC)
    fingerprint = bytes(wally.bip32_key_get_fingerprint(root)).hex()
    key = f"[{fingerprint}/{path}]{xpub}/{{0,1}}/*"
    return template.format(key=key), f"m/{path}"


def encrypt_mnemonic(mnemonic: str, key: bytes, context: bytes) -> str:
    cipher = AES.new(key, AES.MODE_GCM, nonce=secrets.token_bytes(12))
    cipher.update(context)
    ciphertext, tag = cipher.encrypt_and_digest(mnemonic.encode())
    return base64.b64encode(b"\x01" + cipher.nonce + tag + ciphertext).decode()


def decrypt_mnemonic(encrypted: str, key: bytes, context: bytes) -> str:
    raw = base64.b64decode(encrypted, validate=True)
    if len(raw) < 30 or raw[0] != 1:
        raise ValueError("Invalid encrypted wallet")
    cipher = AES.new(key, AES.MODE_GCM, nonce=raw[1:13])
    cipher.update(context)
    return cipher.decrypt_and_verify(raw[29:], raw[13:29]).decode()


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


def descriptor_type(descriptor: Any) -> str:
    return _SCRIPT_TYPES[wally.scriptpubkey_get_type(descriptor_script(descriptor))]


async def derive_address(masterpub: str, num: int, branch_index: int = 0) -> str:
    return await run_in_threadpool(_derive_address, masterpub, num, branch_index)


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


def add_descriptor_metadata(
    psbt: Any,
    index: int,
    descriptor: Any,
    address_index: int,
    branch_index: int,
    *,
    output: bool = False,
) -> None:
    if isinstance(descriptor, TaprootDescriptor):
        raise ValueError("Only Taproot key-spend descriptors are supported")
    scope = "output" if output else "input"
    spk = descriptor_script(descriptor, address_index, branch_index)
    script_type = wally.scriptpubkey_get_type(spk)
    taproot = script_type == wally.WALLY_SCRIPT_TYPE_P2TR
    depth = 0
    if script_type == wally.WALLY_SCRIPT_TYPE_P2SH:
        depth += 1
        spk = descriptor_script(descriptor, address_index, branch_index, depth)
        getattr(wally, f"psbt_set_{scope}_redeem_script")(psbt, index, spk)
    if wally.scriptpubkey_get_type(spk) == wally.WALLY_SCRIPT_TYPE_P2WSH:
        witness = descriptor_script(descriptor, address_index, branch_index, depth + 1)
        getattr(wally, f"psbt_set_{scope}_witness_script")(psbt, index, witness)

    for key_index in range(wally.descriptor_get_num_keys(descriptor)):
        key = wally.descriptor_get_key(descriptor, key_index)
        child_path = _path(
            wally.descriptor_get_key_child_path_str(descriptor, key_index),
            address_index,
            descriptor_branch(descriptor, branch_index),
        )
        features = wally.descriptor_get_key_features(descriptor, key_index)
        if features & wally.WALLY_MS_IS_PARENTED:
            fingerprint = wally.descriptor_get_key_origin_fingerprint(
                descriptor, key_index
            )
            origin = _path(
                wally.descriptor_get_key_origin_path_str(descriptor, key_index)
            )
        else:
            fingerprint, origin = None, []
        if features & wally.WALLY_MS_IS_RAW:
            pubkey = bytes.fromhex(key)
        else:
            hdkey = wally.bip32_key_from_base58(key)
            if fingerprint is None:
                fingerprint = wally.bip32_key_get_fingerprint(hdkey)
            derived = (
                wally.bip32_key_from_parent_path(
                    hdkey, child_path, wally.BIP32_FLAG_KEY_PUBLIC
                )
                if child_path
                else hdkey
            )
            pubkey = bytes(wally.bip32_key_get_pub_key(derived))
        if fingerprint is None:
            raise ValueError(
                "Signing requires a descriptor with key origin information"
            )
        if taproot:
            xonly = pubkey[1:] if len(pubkey) == 33 else pubkey
            getattr(wally, f"psbt_set_{scope}_taproot_internal_key")(psbt, index, xonly)
            getattr(wally, f"psbt_add_{scope}_taproot_keypath")(
                psbt, index, 0, xonly, None, fingerprint, origin + child_path
            )
        else:
            getattr(wally, f"psbt_add_{scope}_keypath")(
                psbt, index, pubkey, fingerprint, origin + child_path
            )


def create_psbt(data: CreatePsbt) -> Any:
    descriptors = {
        masterpub.id: parse_key(masterpub.public_key)[0]
        for masterpub in data.masterpubs
    }
    tx = wally.tx_init(2, 0, len(data.inputs), len(data.outputs))
    for inp in data.inputs:
        wally.tx_add_raw_input(
            tx,
            bytes.fromhex(inp.tx_id)[::-1],
            inp.vout,
            wally.WALLY_TX_SEQUENCE_FINAL,
            None,
            None,
            0,
        )
    for out in data.outputs:
        wally.tx_add_raw_output(tx, out.amount, address_script(out.address), 0)
    # Attaching the transaction initializes its keypath maps in Wally 1.5.6.
    psbt = wally.psbt_init(0, 0, 0, 0, 0)
    wally.psbt_set_global_tx(psbt, tx)
    for index, inp in enumerate(data.inputs):
        descriptor = descriptors[inp.wallet]
        spk = descriptor_script(descriptor, inp.address_index, inp.branch_index)
        previous = wally.tx_from_hex(inp.tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
        previous_txid = bytes(wally.tx_get_txid(previous))[::-1].hex()
        if previous_txid != inp.tx_id or not 0 <= inp.vout < wally.tx_get_num_outputs(
            previous
        ):
            raise ValueError("Input transaction does not match its outpoint")
        if (
            bytes(wally.tx_get_output_script(previous, inp.vout)) != spk
            or wally.tx_get_output_satoshi(previous, inp.vout) != inp.amount
        ):
            raise ValueError("Input does not match its wallet descriptor or amount")
        # Keep SegWit PSBTs within the hardware signer's bounded transfer buffer.
        redeem = (
            descriptor_script(descriptor, inp.address_index, inp.branch_index, 1)
            if wally.scriptpubkey_get_type(spk) == wally.WALLY_SCRIPT_TYPE_P2SH
            else b""
        )
        if wally.scriptpubkey_get_type(redeem or spk) in (
            wally.WALLY_SCRIPT_TYPE_P2WPKH,
            wally.WALLY_SCRIPT_TYPE_P2WSH,
            wally.WALLY_SCRIPT_TYPE_P2TR,
        ):
            wally.psbt_set_input_witness_utxo_from_tx(psbt, index, previous, inp.vout)
        else:
            wally.psbt_set_input_utxo(psbt, index, previous)
        add_descriptor_metadata(
            psbt, index, descriptor, inp.address_index, inp.branch_index
        )

    for index, out in enumerate(data.outputs):
        if out.wallet is None or out.branch_index is None or out.address_index is None:
            continue
        descriptor = descriptors[out.wallet]
        if bytes(wally.tx_get_output_script(tx, index)) != descriptor_script(
            descriptor, out.address_index, out.branch_index
        ):
            raise ValueError("Output does not match its wallet descriptor")
        add_descriptor_metadata(
            psbt, index, descriptor, out.address_index, out.branch_index, output=True
        )
    return psbt


def set_previous_transaction(psbt: Any, index: int, tx_hex: str) -> None:
    previous = wally.tx_from_hex(tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
    vout = wally.psbt_get_input_output_index(psbt, index)
    if bytes(wally.tx_get_txid(previous)) != bytes(
        wally.psbt_get_input_previous_txid(psbt, index)
    ) or not 0 <= vout < wally.tx_get_num_outputs(previous):
        raise ValueError("Input transaction does not match its outpoint")
    witness = wally.psbt_get_input_witness_utxo(psbt, index)
    if witness and (
        bytes(wally.tx_output_get_script(witness))
        != bytes(wally.tx_get_output_script(previous, vout))
        or wally.tx_output_get_satoshi(witness)
        != wally.tx_get_output_satoshi(previous, vout)
    ):
        raise ValueError("Input witness UTXO does not match its previous transaction")
    wally.psbt_set_input_utxo(psbt, index, previous)


def psbt_fee(psbt: Any) -> int:
    amount = sum(
        wally.tx_output_get_satoshi(wally.psbt_get_input_best_utxo(psbt, index))
        for index in range(wally.psbt_get_num_inputs(psbt))
    )
    tx = wally.psbt_extract(psbt, wally.WALLY_PSBT_EXTRACT_NON_FINAL)
    return amount - wally.tx_get_total_output_satoshi(tx)


def combine_matching_psbt(expected: Any, signed: Any) -> Any:
    def unsigned_transaction(psbt: Any) -> str:
        # Final scripts must not participate in the transaction comparison.
        normalized = wally.psbt_clone(psbt, 0)
        wally.psbt_set_version(normalized, 0, 0)
        tx = wally.psbt_get_global_tx(normalized)
        return wally.tx_to_hex(tx, 0)

    if unsigned_transaction(expected) != unsigned_transaction(signed):
        raise ValueError("Signed PSBT does not match the transaction under review")
    wally.psbt_combine(expected, signed)
    return expected


def finalize_signed_psbt(psbt: Any) -> Any:  # noqa: C901
    # Finalization assembles witnesses; it does not verify signatures.
    verification = wally.psbt_clone(psbt, 0)
    tx = wally.psbt_extract(verification, wally.WALLY_PSBT_EXTRACT_NON_FINAL)
    for index, signatures in enumerate(_input_partial_signatures(verification)):
        if not signatures:
            continue
        script = wally.psbt_get_input_signing_script(verification, index)
        scriptcode = wally.psbt_get_input_scriptcode(verification, index, script)
        for pubkey, signature in signatures.items():
            if not signature or signature[-1] not in (1, 2, 3, 0x81, 0x82, 0x83):
                raise ValueError("Invalid ECDSA sighash")
            wally.psbt_set_input_sighash(verification, index, signature[-1])
            digest = wally.psbt_get_input_signature_hash(
                verification, index, tx, scriptcode, 0
            )
            try:
                compact = wally.ec_sig_from_der(signature[:-1])
                wally.ec_sig_verify(pubkey, digest, wally.EC_FLAG_ECDSA, compact)
            except ValueError as exc:
                raise ValueError("Invalid ECDSA signature") from exc
    for index in range(wally.psbt_get_num_inputs(verification)):
        signature = bytes(wally.psbt_get_input_taproot_signature(verification, index))
        if not signature:
            continue
        utxo = wally.psbt_get_input_best_utxo(verification, index)
        spk = bytes(wally.tx_output_get_script(utxo))
        is_taproot = wally.scriptpubkey_get_type(spk) == wally.WALLY_SCRIPT_TYPE_P2TR
        if not is_taproot or len(signature) not in (64, 65):
            raise ValueError("Invalid Taproot key signature")
        sighash = signature[64] if len(signature) == 65 else 0
        if len(signature) == 65 and sighash not in (1, 2, 3, 0x81, 0x82, 0x83):
            raise ValueError("Invalid Taproot sighash")
        wally.psbt_set_input_sighash(verification, index, sighash)
        digest = wally.psbt_get_input_signature_hash(verification, index, tx, None, 0)
        try:
            wally.ec_sig_verify(spk[2:], digest, wally.EC_FLAG_SCHNORR, signature[:64])
        except ValueError as exc:
            raise ValueError("Invalid Taproot key signature") from exc
    wally.psbt_finalize(psbt, 0)
    if not wally.psbt_is_finalized(psbt):
        raise ValueError("PSBT cannot be finalized!")
    return wally.psbt_extract(psbt, 0)


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


def _taproot_hash(tree: Any, address_index: int, branch_index: int) -> bytes:
    if isinstance(tree, tuple):
        children = sorted(_taproot_hash(t, address_index, branch_index) for t in tree)
        return bytes(wally.bip340_tagged_hash(b"".join(children), "TapBranch"))
    script = descriptor_script(tree, address_index, branch_index)
    serialized = b"\xc0" + bytes(wally.varint_to_bytes(len(script))) + script
    return bytes(wally.bip340_tagged_hash(serialized, "TapLeaf"))


def _derive_address(masterpub: str, num: int, branch_index: int) -> str:
    descriptor, _ = parse_key(masterpub)
    return script_address(
        descriptor_script(descriptor, num, branch_index),
        wally.descriptor_get_network(_native_descriptor(descriptor)),
    )


def _path(path: str, address_index: int = 0, branch_index: int = 0) -> list[int]:
    if not path:
        return []
    return wally.bip32_path_from_str(
        path,
        address_index if "*" in path else 0,
        branch_index if "<" in path else 0,
        wally.BIP32_FLAG_STR_WILDCARD | wally.BIP32_FLAG_STR_MULTIPATH,
    )


def _input_partial_signatures(psbt: Any) -> list[dict[bytes, bytes]]:
    # The Python Wally bindings expose signature values but not their public
    # keys. Read those keys from Wally's validated, canonical serialization.
    stream = BytesIO(bytes(wally.psbt_to_bytes(psbt, 0)))
    stream.read(5)  # PSBT magic

    def read_exact(size: int) -> bytes:
        value = stream.read(size)
        if len(value) != size:
            raise ValueError("Invalid PSBT map")
        return value

    def compact_size() -> int:
        prefix = read_exact(1)[0]
        if prefix < 253:
            return prefix
        return int.from_bytes(read_exact({253: 2, 254: 4, 255: 8}[prefix]), "little")

    def read_map() -> dict[bytes, bytes]:
        entries = {}
        while size := compact_size():
            key = read_exact(size)
            entries[key] = read_exact(compact_size())
        return entries

    read_map()  # Global map
    return [
        {key[1:]: value for key, value in read_map().items() if key[0] == 2}
        for _ in range(wally.psbt_get_num_inputs(psbt))
    ]
