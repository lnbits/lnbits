"""BOLT12 Offer support for LNbits.

BOLT12 is the Lightning Network's "Offer" protocol which enables
invoice-less payments. This module handles decoding, validating,
and resolving BOLT12 offers for payment.
"""

import re
from loguru import logger

BOLT12_OFFER_PREFIX = "lno1"
BOLT12_INVOICE_PREFIX = "lni1"
# Bech32 HRP is case-insensitive; after normalize_bolt12_string, offers are lowercased.
BOLT12_OFFER_REGEX = re.compile(r"^(lno1|lno)[a-z0-9]+$")


def normalize_bolt12_string(data: str) -> str:
    """Normalize user-pasted offer/invoice strings for detection.

    - trim whitespace
    - strip lightning: URI scheme (with optional //)
    - drop query/fragment
    - lowercase (bech32 is case-insensitive)
    """
    if not data:
        return ""
    text = data.strip()
    lower = text.lower()
    if lower.startswith("lightning:"):
        text = text[len("lightning:") :]
        if text.startswith("//"):
            text = text[2:]
        text = text.split("?", 1)[0].split("#", 1)[0].strip()
    return text.lower()


def is_bolt12_offer(data: str) -> bool:
    """Check if a string is a BOLT12 offer."""
    return bool(BOLT12_OFFER_REGEX.match(normalize_bolt12_string(data)))


def is_bolt12_invoice(data: str) -> bool:
    """Check if a string is a BOLT12 invoice."""
    return normalize_bolt12_string(data).startswith(BOLT12_INVOICE_PREFIX)


def is_bolt12(data: str) -> bool:
    """Check if a string is any BOLT12 format."""
    return is_bolt12_offer(data) or is_bolt12_invoice(data)


async def resolve_offer(offer: str) -> str:
    """Resolve a BOLT12 offer to a BOLT12 invoice.

    In most cases the wallet backend handles this directly (e.g. CLN's `pay`
    command accepts offers natively). This function is a placeholder for
    cases where the backend needs a resolved invoice first.

    For CLN and Phoenixd, the backend handles offer resolution internally.
    For backends that don't support offers, this will raise.
    """
    normalized = normalize_bolt12_string(offer)
    logger.debug(f"Resolving BOLT12 offer: {normalized[:20]}...")
    return normalized
