# type: ignore

import bitstring
import re
from bech32 import bech32_decode, CHARSET


class Invoice(object):
    def __init__(self):
        self.payment_hash: str = None
        self.amount_msat: int = 0
        self.description: str = None


def decode(pr: str) -> Invoice:
    """ Super naïve bolt11 decoder,
    only gets payment_hash, description/description_hash and amount in msatoshi.
    based on https://github.com/rustyrussell/lightning-payencode/blob/master/lnaddr.py
    """
    hrp, data = bech32_decode(pr)
    if not hrp:
        raise ValueError("Bad bech32 checksum")

    if not hrp.startswith("ln"):
        raise ValueError("Does not start with ln")

    data = u5_to_bitarray(data)

    # Final signature 65 bytes, split it off.
    if len(data) < 65 * 8:
        raise ValueError("Too short to contain signature")
    data = bitstring.ConstBitStream(data[: -65 * 8])

    invoice = Invoice()

    m = re.search("[^\d]+", hrp[2:])
    if m:
        amountstr = hrp[2 + m.end() :]
        if amountstr != "":
            invoice.amount_msat = unshorten_amount(amountstr)

    # pull out date
    data.read(35).uint

    while data.pos != data.len:
        tag, tagdata, data = pull_tagged(data)

        data_length = len(tagdata) / 5

        if tag == "d":
            invoice.description = trim_to_bytes(tagdata).decode("utf-8")
        elif tag == "h" and data_length == 52:
            invoice.description = trim_to_bytes(tagdata).hex()
        elif tag == "p" and data_length == 52:
            invoice.payment_hash = trim_to_bytes(tagdata).hex()

    return invoice


def unshorten_amount(amount: str) -> int:
    """ Given a shortened amount, return millisatoshis
    """
    # BOLT #11:
    # The following `multiplier` letters are defined:
    #
    # * `m` (milli): multiply by 0.001
    # * `u` (micro): multiply by 0.000001
    # * `n` (nano): multiply by 0.000000001
    # * `p` (pico): multiply by 0.000000000001
    units = {
        "p": 10 ** 12,
        "n": 10 ** 9,
        "u": 10 ** 6,
        "m": 10 ** 3,
    }
    unit = str(amount)[-1]

    # BOLT #11:
    # A reader SHOULD fail if `amount` contains a non-digit, or is followed by
    # anything except a `multiplier` in the table above.
    if not re.fullmatch("\d+[pnum]?", str(amount)):
        raise ValueError("Invalid amount '{}'".format(amount))

    if unit in units:
        return int(amount[:-1]) * 100_000_000_000 / units[unit]
    else:
        return int(amount) * 100_000_000_000


def pull_tagged(stream):
    tag = stream.read(5).uint
    length = stream.read(5).uint * 32 + stream.read(5).uint
    return (CHARSET[tag], stream.read(length * 5), stream)


def trim_to_bytes(barr):
    # Adds a byte if necessary.
    b = barr.tobytes()
    if barr.len % 8 != 0:
        return b[:-1]
    return b


def u5_to_bitarray(arr):
    ret = bitstring.BitArray()
    for a in arr:
        ret += bitstring.pack("uint:5", a)
    return ret
