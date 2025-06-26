import base64
import hashlib
import json
import re
from typing import Union
from urllib.parse import urlparse

import secp256k1
from bech32 import bech32_decode, bech32_encode, convertbits
from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from pynostr.key import PrivateKey


def generate_keypair() -> tuple[str, str]:
    private_key = PrivateKey()
    public_key = private_key.public_key
    return private_key.hex(), public_key.hex()


def encrypt_content(
    content: str, service_pubkey: secp256k1.PublicKey, account_private_key_hex: str
) -> str:
    """
    Encrypts the content to be sent to the service.

    Args:
        content (str): The content to be encrypted.
        service_pubkey (secp256k1.PublicKey): The service provider's public key.
        account_private_key_hex (str): The account private key in hex format.

    Returns:
        str: The encrypted content.
    """
    shared = service_pubkey.tweak_mul(
        bytes.fromhex(account_private_key_hex)
    ).serialize()[1:]
    # random iv (16B)
    iv = Random.new().read(AES.block_size)
    aes = AES.new(shared, AES.MODE_CBC, iv)

    content_bytes = content.encode("utf-8")

    # padding
    content_bytes = pad(content_bytes, AES.block_size)

    # Encrypt
    encrypted_b64 = base64.b64encode(aes.encrypt(content_bytes)).decode("ascii")
    iv_b64 = base64.b64encode(iv).decode("ascii")
    encrypted_content = encrypted_b64 + "?iv=" + iv_b64
    return encrypted_content


def decrypt_content(
    content: str, service_pubkey: secp256k1.PublicKey, account_private_key_hex: str
) -> str:
    """
    Decrypts the content coming from the service.

    Args:
        content (str): The encrypted content.
        service_pubkey (secp256k1.PublicKey): The service provider's public key.
        account_private_key_hex (str): The account private key in hex format.

    Returns:
        str: The decrypted content.
    """
    shared = service_pubkey.tweak_mul(
        bytes.fromhex(account_private_key_hex)
    ).serialize()[1:]
    # extract iv and content
    (encrypted_content_b64, iv_b64) = content.split("?iv=")
    encrypted_content = base64.b64decode(encrypted_content_b64.encode("ascii"))
    iv = base64.b64decode(iv_b64.encode("ascii"))
    # Decrypt
    aes = AES.new(shared, AES.MODE_CBC, iv)
    decrypted_bytes = aes.decrypt(encrypted_content)
    decrypted_bytes = unpad(decrypted_bytes, AES.block_size)
    decrypted = decrypted_bytes.decode("utf-8")

    return decrypted


def verify_event(event: dict) -> bool:
    """
    Verify the event signature

    Args:
        event (Dict): The event to verify.

    Returns:
        bool: True if the event signature is valid, False otherwise.
    """
    signature_data = json_dumps(
        [
            0,
            event["pubkey"],
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"],
        ]
    )
    event_id = hashlib.sha256(signature_data.encode()).hexdigest()
    if event_id != event["id"]:
        return False
    pubkey_hex = event["pubkey"]
    pubkey = secp256k1.PublicKey(bytes.fromhex("02" + pubkey_hex), True)
    if not pubkey.schnorr_verify(
        bytes.fromhex(event_id), bytes.fromhex(event["sig"]), None, raw=True
    ):
        return False
    return True


def sign_event(
    event: dict, account_public_key_hex: str, account_private_key: secp256k1.PrivateKey
) -> dict:
    """
    Signs the event (in place) with the service secret

    Args:
        event (Dict): The event to be signed.
        account_public_key_hex (str): The account public key in hex format.
        account_private_key (secp256k1.PrivateKey): The account private key.

    Returns:
        Dict: The input event with the signature added.
    """
    signature_data = json_dumps(
        [
            0,
            account_public_key_hex,
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"],
        ]
    )
    event_id = hashlib.sha256(signature_data.encode()).hexdigest()
    event["id"] = event_id
    event["pubkey"] = account_public_key_hex

    signature = (
        account_private_key.schnorr_sign(bytes.fromhex(event_id), None, raw=True)
    ).hex()
    event["sig"] = signature
    return event


def json_dumps(data: Union[dict, list]) -> str:
    """
    Converts a Python dictionary to a JSON string with compact encoding.

    Args:
        data (Dict): The dictionary to be converted.

    Returns:
        str: The compact JSON string.
    """
    if isinstance(data, dict):
        data = {k: v for k, v in data.items() if v is not None}
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def normalize_public_key(key: str) -> str:
    return normalize_bech32_key("npub1", key)


def normalize_private_key(key: str) -> str:
    return normalize_bech32_key("nsec1", key)


def normalize_bech32_key(hrp: str, key: str) -> str:
    if key.startswith(hrp):
        _, decoded_data = bech32_decode(key)
        assert decoded_data, f"Key is not valid {hrp}."

        decoded_data_bits = convertbits(decoded_data, 5, 8, False)
        assert decoded_data_bits, f"Key is not valid {hrp}."

        return bytes(decoded_data_bits).hex()

    assert len(key) == 64, "Key has wrong length."
    try:
        int(key, 16)
    except Exception as exc:
        raise AssertionError("Key is not valid hex.") from exc
    return key


def hex_to_npub(hex_pubkey: str) -> str:
    """
    Converts a hex public key to a Nostr public key.

    Args:
        hex_pubkey (str): The hex public key to convert.

    Returns:
        str: The Nostr public key.
    """
    normalize_public_key(hex_pubkey)
    pubkey_bytes = bytes.fromhex(hex_pubkey)
    bits = convertbits(pubkey_bytes, 8, 5, True)
    assert bits
    return bech32_encode("npub", bits)


def normalize_identifier(identifier: str):
    identifier = identifier.lower().split("@")[0]
    validate_identifier(identifier)
    return identifier


def validate_pub_key(pubkey: str) -> str:
    if pubkey.startswith("npub"):
        _, data = bech32_decode(pubkey)
        if data:
            decoded_data = convertbits(data, 5, 8, False)
            if decoded_data:
                pubkey = bytes(decoded_data).hex()
    try:
        _hex = bytes.fromhex(pubkey)
    except Exception as exc:
        raise ValueError("Pubkey must be in npub or hex format.") from exc

    if len(_hex) != 32:
        raise ValueError("Pubkey length incorrect.")

    return pubkey


def validate_identifier(local_part: str):
    regex = re.compile(r"^[a-z0-9_.]+$")
    if not re.fullmatch(regex, local_part.lower()):
        raise ValueError(
            f"Identifier '{local_part}' not allowed! "
            "Only a-z, 0-9 and .-_ are allowed characters, case insensitive."
        )


def is_ws_url(url):
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False
        return result.scheme in ["ws", "wss"]
    except ValueError:
        return False
