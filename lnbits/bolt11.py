import bitstring  # type: ignore
import re
import hashlib
from typing import List, NamedTuple, Optional
from bech32 import bech32_decode, CHARSET  # type: ignore
from ecdsa import SECP256k1, VerifyingKey  # type: ignore
from ecdsa.util import sigdecode_string  # type: ignore
from binascii import unhexlify


class Route(NamedTuple):
    pubkey: str
    short_channel_id: str
    base_fee_msat: int
    ppm_fee: int
    cltv: int


class Invoice(object):
    payment_hash: str
    amount_msat: int = 0
    description: Optional[str] = None
    description_hash: Optional[str] = None
    payee: Optional[str] = None
    date: int
    expiry: int = 3600
    secret: Optional[str] = None
    route_hints: List[Route] = []
    min_final_cltv_expiry: int = 18


def decode(pr: str) -> Invoice:
    """bolt11 decoder,
    based on https://github.com/rustyrussell/lightning-payencode/blob/master/lnaddr.py
    """

    hrp, decoded_data = bech32_decode(pr)
    if hrp is None or decoded_data is None:
        raise ValueError("Bad bech32 checksum")
    if not hrp.startswith("ln"):
        raise ValueError("Does not start with ln")

    bitarray = _u5_to_bitarray(decoded_data)

    # final signature 65 bytes, split it off.
    if len(bitarray) < 65 * 8:
        raise ValueError("Too short to contain signature")

    # extract the signature
    signature = bitarray[-65 * 8 :].tobytes()

    # the tagged fields as a bitstream
    data = bitstring.ConstBitStream(bitarray[: -65 * 8])

    # build the invoice object
    invoice = Invoice()

    # decode the amount from the hrp
    m = re.search("[^\d]+", hrp[2:])
    if m:
        amountstr = hrp[2 + m.end() :]
        if amountstr != "":
            invoice.amount_msat = _unshorten_amount(amountstr)

    # pull out date
    invoice.date = data.read(35).uint

    while data.pos != data.len:
        tag, tagdata, data = _pull_tagged(data)
        data_length = len(tagdata) / 5

        if tag == "d":
            invoice.description = _trim_to_bytes(tagdata).decode("utf-8")
        elif tag == "h" and data_length == 52:
            invoice.description_hash = _trim_to_bytes(tagdata).hex()
        elif tag == "p" and data_length == 52:
            invoice.payment_hash = _trim_to_bytes(tagdata).hex()
        elif tag == "x":
            invoice.expiry = tagdata.uint
        elif tag == "n":
            invoice.payee = _trim_to_bytes(tagdata).hex()
            # this won't work in most cases, we must extract the payee
            # from the signature
        elif tag == "s":
            invoice.secret = _trim_to_bytes(tagdata).hex()
        elif tag == "r":
            s = bitstring.ConstBitStream(tagdata)
            while s.pos + 264 + 64 + 32 + 32 + 16 < s.len:
                route = Route(
                    pubkey=s.read(264).tobytes().hex(),
                    short_channel_id=_readable_scid(s.read(64).intbe),
                    base_fee_msat=s.read(32).intbe,
                    ppm_fee=s.read(32).intbe,
                    cltv=s.read(16).intbe,
                )
                invoice.route_hints.append(route)

    # BOLT #11:
    # A reader MUST check that the `signature` is valid (see the `n` tagged
    # field specified below).
    # A reader MUST use the `n` field to validate the signature instead of
    # performing signature recovery if a valid `n` field is provided.
    message = bytearray([ord(c) for c in hrp]) + data.tobytes()
    sig = signature[0:64]
    if invoice.payee:
        key = VerifyingKey.from_string(unhexlify(invoice.payee), curve=SECP256k1)
        key.verify(sig, message, hashlib.sha256, sigdecode=sigdecode_string)
    else:
        keys = VerifyingKey.from_public_key_recovery(
            sig, message, SECP256k1, hashlib.sha256
        )
        signaling_byte = signature[64]
        key = keys[int(signaling_byte)]
        invoice.payee = key.to_string("compressed").hex()

    return invoice


def _unshorten_amount(amount: str) -> int:
    """Given a shortened amount, return millisatoshis"""
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
        return int(int(amount[:-1]) * 100_000_000_000 / units[unit])
    else:
        return int(amount) * 100_000_000_000


def _pull_tagged(stream):
    tag = stream.read(5).uint
    length = stream.read(5).uint * 32 + stream.read(5).uint
    return (CHARSET[tag], stream.read(length * 5), stream)


def _trim_to_bytes(barr):
    # Adds a byte if necessary.
    b = barr.tobytes()
    if barr.len % 8 != 0:
        return b[:-1]
    return b


def _readable_scid(short_channel_id: int) -> str:
    return "{blockheight}x{transactionindex}x{outputindex}".format(
        blockheight=((short_channel_id >> 40) & 0xFFFFFF),
        transactionindex=((short_channel_id >> 16) & 0xFFFFFF),
        outputindex=(short_channel_id & 0xFFFF),
    )


def _u5_to_bitarray(arr: List[int]) -> bitstring.BitArray:
    ret = bitstring.BitArray()
    for a in arr:
        ret += bitstring.pack("uint:5", a)
    return ret
