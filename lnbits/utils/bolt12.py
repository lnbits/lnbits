"""BOLT12 offer validation and simulated invoice encoding.

Offers use the bech32 alphabet with HRP ``lno``, without a checksum. This module
normalizes offers and reads their metadata; invoice fetch and payment stay
on the funding source (see ``Wallet.pay_offer``).
"""

from __future__ import annotations

import hmac
import re
import struct
from hashlib import sha256
from os import urandom
from time import time

from bech32 import CHARSET, convertbits
from coincurve import PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
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


def _create_fake_bolt12_invoice(
    private_key: str,
    payment_hash: str,
    amount_msat: int,
    description: str,
    payer_note: str | None = None,
) -> str:
    """Create a decodable invoice signed by FakeWallet, not the offer's issuer.

    Its single-hop path points to FakeWallet's synthetic node. It describes a
    simulated payment and cannot receive payments on the Lightning network.
    The original external offer is retained separately by the payment service.
    """
    key = PrivateKey.from_hex(private_key)
    node_id = key.public_key.format()
    invoice_hash = bytes.fromhex(payment_hash)

    path_key = PrivateKey()
    shared_secret = path_key.ecdh(node_id)
    rho = hmac.digest(b"rho", shared_secret, "sha256")
    blinded_node_id = key.public_key.multiply(
        hmac.digest(b"blinded_node_id", shared_secret, "sha256")
    ).format()
    recipient_data = _tlv(6, invoice_hash) + _tlv(12, b"\xff" * 4 + b"\x01")
    encrypted_data = ChaCha20Poly1305(rho).encrypt(bytes(12), recipient_data, b"")
    path = (
        node_id
        + path_key.public_key.format()
        + b"\x01"  # one blinded hop
        + blinded_node_id
        + len(encrypted_data).to_bytes(2, "big")
        + encrypted_data
    )
    # Zero fees, 18-block final CLTV delta, and no required features.
    payinfo = struct.pack(">IIHQQH", 0, 0, 18, 1, (1 << 64) - 1, 0)
    fields = {
        0: urandom(32),  # invreq_metadata
        10: description.encode(),  # offer_description
        18: b"FakeWallet",  # offer_issuer
        22: node_id,  # offer_issuer_id
        82: _tu64(amount_msat),  # invreq_amount
        88: PrivateKey().public_key.format(),  # invreq_payer_id
        160: path,  # invoice_paths
        162: payinfo,  # invoice_blindedpay
        164: _tu64(int(time())),  # invoice_created_at
        168: invoice_hash,  # invoice_payment_hash
        170: _tu64(amount_msat),  # invoice_amount
        176: node_id,  # invoice_node_id
    }
    if payer_note:
        fields[89] = payer_note.encode()
    records = [
        (field_type, _tlv(field_type, value))
        for field_type, value in sorted(fields.items())
    ]
    signature_hash = _tagged_hash(b"lightninginvoicesignature", _merkle_root(records))
    payload = b"".join(record for _, record in records) + _tlv(
        240, key.sign_schnorr(signature_hash)
    )
    encoded = convertbits(payload, 8, 5)
    assert encoded is not None
    # BOLT12 uses the bech32 alphabet without its checksum.
    return "lni1" + "".join(CHARSET[value] for value in encoded)


def _tu64(value: int) -> bytes:
    return value.to_bytes(8, "big").lstrip(b"\x00")


def _bigsize(value: int) -> bytes:
    if value < 253:
        return bytes([value])
    for prefix, size in ((253, 2), (254, 4), (255, 8)):
        if value < 1 << (size * 8):
            return bytes([prefix]) + value.to_bytes(size, "big")
    raise ValueError("BigSize value exceeds uint64")


def _tlv(field_type: int, value: bytes) -> bytes:
    return _bigsize(field_type) + _bigsize(len(value)) + value


def _tagged_hash(tag: bytes, message: bytes) -> bytes:
    tag_hash = sha256(tag).digest()
    return sha256(tag_hash + tag_hash + message).digest()


def _merkle_root(records: list[tuple[int, bytes]]) -> bytes:
    """BOLT12's TLV Merkle tree, with each leaf paired with a nonce leaf."""
    nonce_tag = b"LnNonce" + records[0][1]
    leaves = []
    for field_type, record in records:
        pair = sorted(
            (
                _tagged_hash(b"LnLeaf", record),
                _tagged_hash(nonce_tag, _bigsize(field_type)),
            )
        )
        leaves.append(_tagged_hash(b"LnBranch", b"".join(pair)))
    while len(leaves) > 1:
        branches = [
            _tagged_hash(b"LnBranch", b"".join(sorted(leaves[i : i + 2])))
            for i in range(0, len(leaves) - 1, 2)
        ]
        if len(leaves) % 2:
            branches.append(leaves[-1])
        leaves = branches
    return leaves[0]
