import base64
import getpass
from hashlib import md5, pbkdf2_hmac, sha256

from Cryptodome import Random
from Cryptodome.Cipher import AES

BLOCK_SIZE = 16


def random_secret_and_hash() -> tuple[str, str]:
    secret = Random.new().read(32)
    return secret.hex(), sha256(secret).hexdigest()


def fake_privkey(secret: str) -> str:
    return pbkdf2_hmac(
        "sha256",
        secret.encode(),
        b"FakeWallet",
        2048,
        32,
    ).hex()


class AESCipher:
    """This class is compatible with crypto-js/aes.js

    Encrypt and decrypt in Javascript using:
        import AES from "crypto-js/aes.js";
        import Utf8 from "crypto-js/enc-utf8.js";
        AES.encrypt(decrypted, password).toString()
        AES.decrypt(encrypted, password).toString(Utf8);

    """

    def __init__(self, key=None, description=""):
        self.key = key
        self.description = description + " "

    def pad(self, data):
        length = BLOCK_SIZE - (len(data) % BLOCK_SIZE)
        return data + (chr(length) * length).encode()

    def unpad(self, data):
        return data[: -(data[-1] if isinstance(data[-1], int) else ord(data[-1]))]

    @property
    def passphrase(self):
        passphrase = self.key if self.key is not None else None
        if passphrase is None:
            passphrase = getpass.getpass(f"Enter {self.description}password:")
        return passphrase

    def bytes_to_key(self, data, salt, output=48):
        # extended from https://gist.github.com/gsakkis/4546068
        assert len(salt) == 8, len(salt)
        data += salt
        key = md5(data).digest()
        final_key = key
        while len(final_key) < output:
            key = md5(key + data).digest()
            final_key += key
        return final_key[:output]

    def decrypt(self, encrypted: str) -> str:
        """Decrypts a string using AES-256-CBC."""
        passphrase = self.passphrase
        encrypted_bytes = base64.b64decode(encrypted)
        assert encrypted_bytes[0:8] == b"Salted__"
        salt = encrypted_bytes[8:16]
        key_iv = self.bytes_to_key(passphrase.encode(), salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
        aes = AES.new(key, AES.MODE_CBC, iv)
        try:
            return self.unpad(aes.decrypt(encrypted_bytes[16:])).decode()
        except UnicodeDecodeError as exc:
            raise ValueError("Wrong passphrase") from exc

    def encrypt(self, message: bytes) -> str:
        passphrase = self.passphrase
        salt = Random.new().read(8)
        key_iv = self.bytes_to_key(passphrase.encode(), salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
        aes = AES.new(key, AES.MODE_CBC, iv)
        return base64.b64encode(
            b"Salted__" + salt + aes.encrypt(self.pad(message))
        ).decode()
