"""BOLT12 offer detection and fail-closed validation.

Offers use the bech32 alphabet with HRP ``lno``, without a checksum. This module
normalizes offers and reads their metadata; invoice fetch and payment stay
on the funding source (see ``Wallet.pay_offer``).
"""

from __future__ import annotations

import re

from bech32 import CHARSET, convertbits
from pydantic import BaseModel

from lnbits.exceptions import PaymentError

# Bech32 data alphabet (BIP-173): 0-9 / a-z minus 1, b, i, o.
_BECH32_DATA_RE = re.compile(r"^[ac-hj-np-z02-9]+$")
_BOLT12_PRETTY_PLUS = re.compile(r"\+\s*")

# Basic sanity check; semantic offer validation stays on the funding source.
_MIN_OFFER_LEN = 10


class DecodedBolt12Offer(BaseModel):
    offer: str
    # Millisatoshis without a currency, otherwise the currency's minor units.
    amount: int | None = None
    currency: str | None = None
    description: str | None = None


def normalize_bolt12_input(value: str) -> str:
    """Strip URI wrappers and BOLT12 pretty-print marks; keep original case."""
    text = (value or "").strip()
    if not text:
        return ""

    lowered = text.lower()
    if lowered.startswith("lightning:"):
        text = text[len("lightning:") :]
        if text.startswith("//"):
            text = text[2:]
        text = text.split("?", 1)[0].split("#", 1)[0].strip()

    # BOLT12 writers may insert '+' and following whitespace for wrapping.
    return _BOLT12_PRETTY_PLUS.sub("", text).strip()


def looks_like_bolt12_offer(value: str) -> bool:
    """True when the string is intended as an offer (HRP ``lno``).

    Used to fail closed on malformed ``lno…`` input instead of falling through
    to BOLT11 decoding.
    """
    text = normalize_bolt12_input(value).lower()
    return text.startswith("lno")


def parse_bolt12_offer(value: str) -> str:
    """Return a normalized offer or raise ``PaymentError``."""
    raw = normalize_bolt12_input(value)
    if not raw:
        raise PaymentError("Invalid BOLT12 offer.", status="failed")

    if raw != raw.lower() and raw != raw.upper():
        raise PaymentError("Invalid BOLT12 offer.", status="failed")

    offer = raw.lower()
    hrp, separator, data = offer.partition("1")
    if hrp != "lno" or separator != "1" or not data:
        raise PaymentError("Invalid BOLT12 offer.", status="failed")
    if not _BECH32_DATA_RE.match(data) or len(offer) < _MIN_OFFER_LEN:
        raise PaymentError("Invalid BOLT12 offer.", status="failed")
    return offer


def is_bolt12_offer(value: str) -> bool:
    try:
        parse_bolt12_offer(value)
    except PaymentError:
        return False
    return True


def get_bolt12_offer_description(value: str) -> str | None:
    return decode_bolt12_offer(value).description


def decode_bolt12_offer(value: str) -> DecodedBolt12Offer:
    """Read offer metadata, checking encoding, field formats and TLV boundaries."""
    offer = parse_bolt12_offer(value)
    decoded = convertbits([CHARSET.index(char) for char in offer[4:]], 5, 8, False)
    if decoded is None:
        raise PaymentError("Invalid BOLT12 offer encoding.", status="failed")

    data = bytes(decoded)
    offset = 0
    previous_type = -1
    result = DecodedBolt12Offer(offer=offer)
    try:
        while offset < len(data):
            field_type, offset = _read_bigsize(data, offset)
            length, offset = _read_bigsize(data, offset)
            end = offset + length
            if field_type <= previous_type or end > len(data):
                raise ValueError("Invalid TLV record")
            field = data[offset:end]
            if field_type == 6:
                currency = field.decode("utf-8")
                if not re.fullmatch(r"[A-Z]{3}", currency):
                    raise ValueError("Invalid offer currency")
                result.currency = currency
            elif field_type == 8:
                if not 1 <= length <= 8 or field[0] == 0:
                    raise ValueError("Invalid offer amount")
                result.amount = int.from_bytes(field, "big")
            elif field_type == 10:
                result.description = field.decode("utf-8")
            previous_type = field_type
            offset = end
    except ValueError as exc:
        raise PaymentError("Invalid BOLT12 offer data.", status="failed") from exc
    return result


def _read_bigsize(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data):
        raise ValueError("Missing BigSize value")
    prefix = data[offset]
    offset += 1
    if prefix < 253:
        return prefix, offset

    size = 1 << (prefix - 252)
    end = offset + size
    if end > len(data):
        raise ValueError("Truncated BigSize value")
    value = int.from_bytes(data[offset:end], "big")
    if value < {253: 253, 254: 0x10000, 255: 0x100000000}[prefix]:
        raise ValueError("Non-canonical BigSize value")
    return value, end
