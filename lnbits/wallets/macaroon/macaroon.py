import base64
from getpass import getpass
from typing import Optional

from lnbits.utils.crypto import AESCipher


def load_macaroon(
    macaroon: Optional[str] = None,
    encrypted_macaroon: Optional[str] = None,
) -> str:
    """Returns hex version of a macaroon encoded in base64 or the file path."""

    if macaroon is None and encrypted_macaroon is None:
        raise ValueError("Either macaroon or encrypted_macaroon must be provided.")

    if encrypted_macaroon:
        # if the macaroon is encrypted, decrypt it and return the hex version
        key = getpass("Enter the macaroon decryption key: ")
        aes = AESCipher(key.encode())
        return aes.decrypt(encrypted_macaroon)

    assert macaroon, "macaroon must be set here"

    # if the macaroon is a file path, load it and return hex version
    if macaroon.split(".")[-1] == "macaroon":
        with open(macaroon, "rb") as f:
            macaroon_bytes = f.read()
            return macaroon_bytes.hex()

    # if macaroon is a provided string check if it is hex, if so, return
    try:
        bytes.fromhex(macaroon)
        return macaroon
    except ValueError:
        pass

    # convert the base64 macaroon to hex
    try:
        macaroon = base64.b64decode(macaroon).hex()
        return macaroon
    except Exception:
        pass

    return macaroon
