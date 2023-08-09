import hashlib
import re
import time
from decimal import Decimal
from typing import List, NamedTuple, Optional

import bitstring
import secp256k1
from bech32 import CHARSET, bech32_decode, bech32_encode
from ecdsa import SECP256k1, VerifyingKey
from ecdsa.util import sigdecode_string


class Route(NamedTuple):
    pubkey: str
    short_channel_id: str
    base_fee_msat: int
    ppm_fee: int
    cltv: int


class Invoice:
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
    m = re.search(r"[^\d]+", hrp[2:])
    if m:
        amountstr = hrp[2 + m.end() :]
        if amountstr != "":
            invoice.amount_msat = _unshorten_amount(amountstr)

    # pull out date
    date_bin = data.read(35)
    invoice.date = date_bin.uint  # type: ignore

    while data.pos != data.len:
        tag, tagdata, data = _pull_tagged(data)
        data_length = len(tagdata or []) / 5

        if tag == "d":
            invoice.description = _trim_to_bytes(tagdata).decode()
        elif tag == "h" and data_length == 52:
            invoice.description_hash = _trim_to_bytes(tagdata).hex()
        elif tag == "p" and data_length == 52:
            invoice.payment_hash = _trim_to_bytes(tagdata).hex()
        elif tag == "x":
            invoice.expiry = tagdata.uint  # type: ignore
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
                    pubkey=s.read(264).tobytes().hex(),  # type: ignore
                    short_channel_id=_readable_scid(s.read(64).intbe),  # type: ignore
                    base_fee_msat=s.read(32).intbe,  # type: ignore
                    ppm_fee=s.read(32).intbe,  # type: ignore
                    cltv=s.read(16).intbe,  # type: ignore
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
        key = VerifyingKey.from_string(bytes.fromhex(invoice.payee), curve=SECP256k1)
        key.verify(sig, message, hashlib.sha256, sigdecode=sigdecode_string)
    else:
        keys = VerifyingKey.from_public_key_recovery(
            sig, message, SECP256k1, hashlib.sha256
        )
        signaling_byte = signature[64]
        key = keys[int(signaling_byte)]
        invoice.payee = key.to_string("compressed").hex()

    return invoice


def encode(options):
    """Convert options into LnAddr and pass it to the encoder"""
    addr = LnAddr()
    addr.currency = options["currency"]
    addr.fallback = options["fallback"] if options["fallback"] else None
    if options["amount"]:
        addr.amount = options["amount"]
    if options["timestamp"]:
        addr.date = int(options["timestamp"])

    addr.paymenthash = bytes.fromhex(options["paymenthash"])

    if options["description"]:
        addr.tags.append(("d", options["description"]))
    if options["description_hash"]:
        addr.tags.append(("h", options["description_hash"]))
    if options["expires"]:
        addr.tags.append(("x", options["expires"]))

    if options["fallback"]:
        addr.tags.append(("f", options["fallback"]))
    if options["route"]:
        for r in options["route"]:
            splits = r.split("/")
            route = []
            while len(splits) >= 5:
                route.append(
                    (
                        bytes.fromhex(splits[0]),
                        bytes.fromhex(splits[1]),
                        int(splits[2]),
                        int(splits[3]),
                        int(splits[4]),
                    )
                )
                splits = splits[5:]
            assert len(splits) == 0
            addr.tags.append(("r", route))
    return lnencode(addr, options["privkey"])


def lnencode(addr, privkey):
    if addr.amount:
        amount = Decimal(str(addr.amount))
        # We can only send down to millisatoshi.
        if amount * 10**12 % 10:
            raise ValueError(f"Cannot encode {addr.amount}: too many decimal places")

        amount = addr.currency + shorten_amount(amount)
    else:
        amount = addr.currency if addr.currency else ""

    hrp = f"ln{amount}0n"

    # Start with the timestamp
    data = bitstring.pack("uint:35", addr.date)

    # Payment hash
    data += tagged_bytes("p", addr.paymenthash)
    tags_set = set()

    for k, v in addr.tags:
        # BOLT #11:
        #
        # A writer MUST NOT include more than one `d`, `h`, `n` or `x` fields,
        if k in ("d", "h", "n", "x"):
            if k in tags_set:
                raise ValueError(f"Duplicate '{k}' tag")

        if k == "r":
            route = bitstring.BitArray()
            for step in v:
                pubkey, channel, feebase, feerate, cltv = step
                route.append(
                    bitstring.BitArray(pubkey)
                    + bitstring.BitArray(channel)
                    + bitstring.pack("intbe:32", feebase)
                    + bitstring.pack("intbe:32", feerate)
                    + bitstring.pack("intbe:16", cltv)
                )
            data += tagged("r", route)
        elif k == "f":
            # NOTE: there was an error fallback here that's now removed
            continue
        elif k == "d":
            data += tagged_bytes("d", v.encode())
        elif k == "x":
            # Get minimal length by trimming leading 5 bits at a time.
            expirybits = bitstring.pack("intbe:64", v)[4:64]
            while expirybits.startswith("0b00000"):
                expirybits = expirybits[5:]
            data += tagged("x", expirybits)
        elif k == "h":
            data += tagged_bytes("h", v)
        elif k == "n":
            data += tagged_bytes("n", v)
        else:
            # FIXME: Support unknown tags?
            raise ValueError(f"Unknown tag {k}")

        tags_set.add(k)

    # BOLT #11:
    #
    # A writer MUST include either a `d` or `h` field, and MUST NOT include
    # both.
    if "d" in tags_set and "h" in tags_set:
        raise ValueError("Cannot include both 'd' and 'h'")
    if "d" not in tags_set and "h" not in tags_set:
        raise ValueError("Must include either 'd' or 'h'")

    # We actually sign the hrp, then data (padded to 8 bits with zeroes).
    privkey = secp256k1.PrivateKey(bytes.fromhex(privkey))
    sig = privkey.ecdsa_sign_recoverable(
        bytearray([ord(c) for c in hrp]) + data.tobytes()
    )
    # This doesn't actually serialize, but returns a pair of values :(
    sig, recid = privkey.ecdsa_recoverable_serialize(sig)
    data += bytes(sig) + bytes([recid])

    return bech32_encode(hrp, bitarray_to_u5(data))


class LnAddr:
    def __init__(
        self,
        paymenthash=None,
        amount=None,
        currency="bc",
        tags=None,
        date=None,
        fallback=None,
    ):
        self.date = int(time.time()) if not date else int(date)
        self.tags = [] if not tags else tags
        self.unknown_tags = []
        self.paymenthash = paymenthash
        self.signature = None
        self.pubkey = None
        self.fallback = fallback
        self.currency = currency
        self.amount = amount

    def __str__(self):
        assert self.pubkey, "LnAddr, pubkey must be set"
        pubkey = bytes.hex(self.pubkey.serialize())
        tags = ", ".join([f"{k}={v}" for k, v in self.tags])
        return f"LnAddr[{pubkey}, amount={self.amount}{self.currency} tags=[{tags}]]"


def shorten_amount(amount):
    """Given an amount in bitcoin, shorten it"""
    # Convert to pico initially
    amount = int(amount * 10**12)
    units = ["p", "n", "u", "m", ""]
    unit = ""
    for unit in units:
        if amount % 1000 == 0:
            amount //= 1000
        else:
            break
    return str(amount) + unit


def _unshorten_amount(amount: str) -> int:
    """Given a shortened amount, return millisatoshis"""
    # BOLT #11:
    # The following `multiplier` letters are defined:
    #
    # * `m` (milli): multiply by 0.001
    # * `u` (micro): multiply by 0.000001
    # * `n` (nano): multiply by 0.000000001
    # * `p` (pico): multiply by 0.000000000001
    units = {"p": 10**12, "n": 10**9, "u": 10**6, "m": 10**3}
    unit = str(amount)[-1]

    # BOLT #11:
    # A reader SHOULD fail if `amount` contains a non-digit, or is followed by
    # anything except a `multiplier` in the table above.
    if not re.fullmatch(r"\d+[pnum]?", str(amount)):
        raise ValueError(f"Invalid amount '{amount}'")

    if unit in units:
        return int(int(amount[:-1]) * 100_000_000_000 / units[unit])
    else:
        return int(amount) * 100_000_000_000


def _pull_tagged(stream):
    tag = stream.read(5).uint
    length = stream.read(5).uint * 32 + stream.read(5).uint
    return (CHARSET[tag], stream.read(length * 5), stream)


# Tagged field containing BitArray
def tagged(char, bits):
    # Tagged fields need to be zero-padded to 5 bits.
    while bits.len % 5 != 0:
        bits.append("0b0")
    return (
        bitstring.pack(
            "uint:5, uint:5, uint:5",
            CHARSET.find(char),
            (bits.len / 5) / 32,
            (bits.len / 5) % 32,
        )
        + bits
    )


def tagged_bytes(char, bits):
    return tagged(char, bitstring.BitArray(bits))


def _trim_to_bytes(barr):
    # Adds a byte if necessary.
    b = barr.tobytes()
    if barr.len % 8 != 0:
        return b[:-1]
    return b


def _readable_scid(short_channel_id: int) -> str:
    blockheight = (short_channel_id >> 40) & 0xFFFFFF
    transactionindex = (short_channel_id >> 16) & 0xFFFFFF
    outputindex = short_channel_id & 0xFFFF
    return f"{blockheight}x{transactionindex}x{outputindex}"


def _u5_to_bitarray(arr: List[int]) -> bitstring.BitArray:
    ret = bitstring.BitArray()
    for a in arr:
        ret += bitstring.pack("uint:5", a)
    return ret


def bitarray_to_u5(barr):
    assert barr.len % 5 == 0
    ret = []
    s = bitstring.ConstBitStream(barr)
    while s.pos != s.len:
        ret.append(s.read(5).uint)  # type: ignore
    return ret
