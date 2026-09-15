"""BOLT12 offer detection and fail-closed validation.

Offers are bech32 strings with HRP ``lno``. This module only identifies and
normalizes an offer string; invoice fetch and payment stay on the funding
source (see ``Wallet.pay_offer``).
"""

from __future__ import annotations

import re

from lnbits.exceptions import PaymentError

# Bech32 data alphabet (BIP-173): 0-9 / a-z minus 1, b, i, o.
_BECH32_DATA_RE = re.compile(r"^[ac-hj-np-z02-9]+$")
_BOLT12_PRETTY_PLUS = re.compile(r"\+\s*")

# HRP + separator + 6-character checksum is the theoretical minimum.
_MIN_OFFER_LEN = 10


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
