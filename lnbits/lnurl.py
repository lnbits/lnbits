from bech32 import bech32_decode, bech32_encode, convertbits


def decode(lnurl: str) -> str:
    hrp, data = bech32_decode(lnurl)
    assert data
    bech32_data = convertbits(data, 5, 8, False)
    assert bech32_data
    return bytes(bech32_data).decode("utf-8")


def encode(url: str) -> str:
    bech32_data = convertbits(url.encode("utf-8"), 8, 5, True)
    assert bech32_data
    lnurl = bech32_encode("lnurl", bech32_data)
    return lnurl.upper()
