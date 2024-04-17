import base64
import getpass
from hashlib import md5

from Cryptodome import Random
from Cryptodome.Cipher import AES

BLOCK_SIZE = 16


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

    def decrypt(self, encrypted: str) -> str:  # type: ignore
        """Decrypts a string using AES-256-CBC."""
        passphrase = self.passphrase
        encrypted = base64.b64decode(encrypted)  # type: ignore
        assert encrypted[0:8] == b"Salted__"
        salt = encrypted[8:16]
        key_iv = self.bytes_to_key(passphrase.encode(), salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
        aes = AES.new(key, AES.MODE_CBC, iv)
        try:
            return self.unpad(aes.decrypt(encrypted[16:])).decode()  # type: ignore
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
