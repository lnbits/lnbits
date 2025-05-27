from base64 import b64decode, b64encode, urlsafe_b64decode, urlsafe_b64encode
from hashlib import md5, pbkdf2_hmac, sha256
from typing import Union

from Cryptodome import Random
from Cryptodome.Cipher import AES


def random_secret_and_hash(length: int = 32) -> tuple[str, str]:
    secret = Random.new().read(length)
    return secret.hex(), sha256(secret).hexdigest()


def fake_privkey(secret: str) -> str:
    return pbkdf2_hmac(
        "sha256",
        secret.encode(),
        b"FakeWallet",
        2048,
        32,
    ).hex()


def verify_preimage(preimage: str, payment_hash: str) -> bool:
    preimage_bytes = bytes.fromhex(preimage)
    calculated_hash = sha256(preimage_bytes).hexdigest()
    return calculated_hash == payment_hash


class AESCipher:
    """
    AES-256-CBC encryption/decryption with salt and base64 encoding.
    :param key: The key to use for en-/decryption. It can be bytes, a hex or a string.

    This class is compatible with crypto-js/aes.js
    Encrypt and decrypt in Javascript using:
    import AES from "crypto-js/aes.js";
    import Utf8 from "crypto-js/enc-utf8.js";
    AES.encrypt(decrypted, password).toString()
    AES.decrypt(encrypted, password).toString(Utf8);
    """

    def __init__(self, key: Union[bytes, str], block_size: int = 16):
        self.block_size = block_size
        if isinstance(key, bytes):
            self.key = key
            return
        try:
            self.key = bytes.fromhex(key)
        except ValueError:
            pass
        self.key = key.encode()

    def pad(self, data: bytes) -> bytes:
        length = self.block_size - (len(data) % self.block_size)
        return data + (chr(length) * length).encode()

    def unpad(self, data: bytes) -> bytes:
        padding = data[-1]
        # Ensure padding is within valid range else there is no padding
        if padding <= 0 or padding >= self.block_size:
            return data
        return data[:-padding]

    def derive_iv_and_key(
        self, salt: bytes, output_len: int = 32 + 16
    ) -> tuple[bytes, bytes]:
        # extended from https://gist.github.com/gsakkis/4546068
        assert len(salt) == 8, "Salt must be 8 bytes"
        data = self.key + salt
        key = md5(data).digest()
        final_key = key
        while len(final_key) < output_len:
            key = md5(key + data).digest()
            final_key += key
        iv_key = final_key[:output_len]
        return iv_key[32:], iv_key[:32]

    def decrypt(self, encrypted: str, urlsafe: bool = False) -> str:
        """Decrypts a salted base64 encoded string using AES-256-CBC."""
        if urlsafe:
            decoded = urlsafe_b64decode(encrypted)
        else:
            decoded = b64decode(encrypted)

        if decoded[0:8] != b"Salted__":
            raise ValueError("Invalid salt.")

        salt = decoded[8:16]
        encrypted_bytes = decoded[16:]

        iv, key = self.derive_iv_and_key(salt, 32 + 16)
        aes = AES.new(key, AES.MODE_CBC, iv)

        try:
            decrypted_bytes = aes.decrypt(encrypted_bytes)
        except Exception as exc:
            raise ValueError("Could not decrypt payload") from exc

        unpadded = self.unpad(decrypted_bytes)
        if len(unpadded) == 0:
            raise ValueError("Unpadding resulted in empty data.")

        try:
            return unpadded.decode()
        except UnicodeDecodeError as exc:
            raise ValueError("Decryption resulted in invalid UTF-8 data.") from exc

    def encrypt(self, message: bytes, urlsafe: bool = False) -> str:
        """
        Encrypts a string using AES-256-CBC and returns a salted base64 encoded string.
        """
        salt = Random.new().read(8)
        iv, key = self.derive_iv_and_key(salt, 32 + 16)
        aes = AES.new(key, AES.MODE_CBC, iv)
        msg = self.pad(message)
        encrypted = aes.encrypt(msg)
        salted = b"Salted__" + salt + encrypted
        encoded = urlsafe_b64encode(salted) if urlsafe else b64encode(salted)
        return encoded.decode()
