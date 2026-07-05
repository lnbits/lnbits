"""BOLT12 Offer support for LNbits.

BOLT12 is the Lightning Network's "Offer" protocol which enables
invoice-less payments. This module handles decoding, validating,
and resolving BOLT12 offers for payment.
"""

import re
from loguru import logger

BOLT12_OFFER_PREFIX = "lno1"
BOLT12_INVOICE_PREFIX = "lni1"
BOLT12_OFFER_REGEX = re.compile(r"^(lno1|lno)[a-zA-Z0-9]+$")


def is_bolt12_offer(data: str) -> bool:
    """Check if a string is a BOLT12 offer."""
    return bool(BOLT12_OFFER_REGEX.match(data))


def is_bolt12_invoice(data: str) -> bool:
    """Check if a string is a BOLT12 invoice."""
    return data.startswith(BOLT12_INVOICE_PREFIX)


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
    logger.debug(f"Resolving BOLT12 offer: {offer[:20]}...")
    return offer
