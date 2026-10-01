"""Mnemonic derivation and authenticated encryption with explicit key material."""

import base64
import secrets

from Cryptodome.Cipher import AES

from .onchain_bindings import wally


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


def wallet_descriptor(mnemonic: str, network: str) -> tuple[str, str]:
    root = root_key(mnemonic, network)
    coin = 0 if network == "Mainnet" else 1
    path = f"84'/{coin}'/0'"
    account = wally.bip32_key_from_parent_path(
        root, [0x80000054, 0x80000000 + coin, 0x80000000], wally.BIP32_FLAG_KEY_PRIVATE
    )
    xpub = wally.bip32_key_to_base58(account, wally.BIP32_FLAG_KEY_PUBLIC)
    fingerprint = bytes(wally.bip32_key_get_fingerprint(root)).hex()
    return f"wpkh([{fingerprint}/{path}]{xpub}/{{0,1}}/*)", f"m/{path}"


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
