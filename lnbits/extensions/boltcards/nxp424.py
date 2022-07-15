# https://www.nxp.com/docs/en/application-note/AN12196.pdf
from typing import Tuple

from Cryptodome.Cipher import AES
from Cryptodome.Hash import CMAC

SV2 = "3CC300010080"


def myCMAC(key: bytes, msg: bytes = b"") -> bytes:
    cobj = CMAC.new(key, ciphermod=AES)
    if msg != b"":
        cobj.update(msg)
    return cobj.digest()


def decryptSUN(sun: bytes, key: bytes) -> Tuple[bytes, bytes]:
    IVbytes = b"\x00" * 16

    cipher = AES.new(key, AES.MODE_CBC, IVbytes)
    sun_plain = cipher.decrypt(sun)

    UID = sun_plain[1:8]
    counter = sun_plain[8:11]

    return UID, counter


def getSunMAC(UID: bytes, counter: bytes, key: bytes) -> bytes:
    sv2prefix = bytes.fromhex(SV2)
    sv2bytes = sv2prefix + UID + counter

    mac1 = myCMAC(key, sv2bytes)
    mac2 = myCMAC(mac1)

    return mac2[1::2]
