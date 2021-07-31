from bech32 import bech32_decode, convertbits


def decode(lnurl: str) -> str:
    hrp, data = bech32_decode(lnurl)
    bech32_data = convertbits(data, 5, 8, False)
    return bytes(bech32_data).decode("utf-8")
