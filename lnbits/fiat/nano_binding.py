"""Nano (XNO) payment-to-order binding for the ``nano:mainnet`` exact scheme.

Standard library only: no key, no seed, no signing, no network. Integer *raw*
throughout (1 XNO = 10**30 raw). This module is the dependency-free core used by
``lnbits/fiat/nano.py``; it can be unit-tested on its own.

It implements Option C of the public binding standard
(https://github.com/dhyabi2/xno-call-binding/blob/main/docs/BINDING-STANDARD.md):
a single fixed ``payTo`` address is configured by the operator, and each order is
bound by a commitment carried in the buyer's send-block ``representative`` field.
The commitment is ``SHA256("xno-binding/v1/rep|" + order_id + "|" + payTo + "|" +
price_raw)`` encoded as a ``nano_`` account, so a confirmed send of exactly
``price_raw`` to ``payTo`` whose representative equals that account proves it was
made for this order, by this buyer, for this amount - with no memo field and no
amount guessing. Each credited block hash is recorded once in a SQLite ledger so
a replay is refused and the refusal survives a restart.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from decimal import Decimal
from typing import NamedTuple

XNO_RAW = 10**30  # raw per 1 XNO
_ALPHA = "13456789abcdefghijkmnopqrstuwxyz"  # Nano base32 alphabet


def _enc32(n: int, chars: int) -> str:
    out = []
    for _ in range(chars):
        out.append(_ALPHA[n & 31])
        n >>= 5
    return "".join(reversed(out))


def pubkey_to_account(pub: bytes) -> str:
    """32-byte public key -> ``nano_`` address (52 key chars + 8 checksum chars)."""
    if len(pub) != 32:
        raise ValueError("public key must be 32 bytes")
    key = _enc32(int.from_bytes(pub, "big"), 52)
    checksum = hashlib.blake2b(pub, digest_size=5).digest()[::-1]
    chk = _enc32(int.from_bytes(checksum, "big"), 8)
    return "nano_" + key + chk


def account_to_pubkey(address: str) -> bytes:
    """Decode a ``nano_`` address and verify its blake2b checksum."""
    if not address.startswith("nano_") or len(address) != 65:
        raise ValueError("address must be 'nano_' + 60 chars")
    body = address[5:]
    if any(ch not in _ALPHA for ch in body):
        raise ValueError("address has a non-base32 character")
    n = 0
    for ch in body[:52]:
        n = n * 32 + _ALPHA.index(ch)
    pub = (n & ((1 << 256) - 1)).to_bytes(32, "big")
    if pubkey_to_account(pub) != address:
        raise ValueError("address checksum mismatch")
    return pub


def is_valid_address(address: str) -> bool:
    """True only for a syntactically valid, checksum-correct ``nano_`` address."""
    try:
        account_to_pubkey(address)
        return True
    except (ValueError, TypeError):
        return False


def xno_to_raw(amount_xno: float | str | Decimal) -> int:
    """Derive the exact raw amount for a positive XNO value (1 XNO = 10**30 raw).

    The raw amount is *derived* here and never restated downstream.
    """
    dec = Decimal(str(amount_xno))
    if not dec.is_finite() or dec <= 0:
        raise ValueError("XNO amount must be a positive finite number")
    raw = dec * XNO_RAW
    if raw != raw.to_integral_value():
        raise ValueError("XNO amount has more precision than 1 raw (10**-30 XNO)")
    return int(raw)


def order_commitment(order_id: str, pay_to: str, price_raw: int) -> bytes:
    """SHA256 commitment binding order id, destination and exact price (raw)."""
    if isinstance(price_raw, bool) or not isinstance(price_raw, int):
        raise TypeError("price_raw must be an int of raw")
    msg = (
        b"xno-binding/v1/rep|"
        + order_id.encode()
        + b"|"
        + pay_to.encode()
        + b"|"
        + str(price_raw).encode()
    )
    return hashlib.sha256(msg).digest()


def commitment_rep_account(order_id: str, pay_to: str, price_raw: int) -> str:
    """The commitment encoded as the ``representative`` the buyer must set."""
    return pubkey_to_account(order_commitment(order_id, pay_to, price_raw))


def payment_uri(pay_to: str, price_raw: int, representative: str) -> str:
    """A ``nano:`` URI naming the exact amount and the required representative.

    Agents paying this scheme sign one send block of ``price_raw`` to ``pay_to``
    with ``representative`` set to the given account; no other field binds it.
    """
    return f"nano:{pay_to}?amount={price_raw}&representative={representative}"


class CreditResult(NamedTuple):
    verdict: str
    order_id: str | None = None

    @property
    def matched(self) -> bool:
        return self.verdict == "matched"


class NanoClaimLedger:
    """Restart-proof, one-to-one ``block_hash -> order_id`` claim store (SQLite).

    ``path`` may be ``":memory:"`` for tests. A UNIQUE index on ``order_id`` keeps
    one credit per order; the ``block_hash`` primary key keeps one credit per block.
    Because it is on disk, a block already credited is still refused after a restart.
    """

    def __init__(self, path: str) -> None:
        # The provider is a long-lived singleton; allow use from the event loop's
        # threadpool and serialize writes with a lock.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS nano_claims("
            "block_hash TEXT PRIMARY KEY, order_id TEXT NOT NULL, "
            "paid_raw TEXT NOT NULL, block_time INTEGER)"
        )
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS nano_one_credit ON nano_claims(order_id)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def verdict_for(self, block_hash: str) -> CreditResult | None:
        row = self._conn.execute(
            "SELECT order_id FROM nano_claims WHERE block_hash=?", (block_hash,)
        ).fetchone()
        if row is None:
            return None
        return CreditResult("matched", row[0])

    def order_credited(self, order_id: str) -> bool:
        """True once any block has been credited to this order (restart-proof)."""
        row = self._conn.execute(
            "SELECT 1 FROM nano_claims WHERE order_id=? LIMIT 1", (order_id,)
        ).fetchone()
        return row is not None

    def credit(
        self,
        *,
        block_hash: str,
        order_id: str,
        pay_to: str,
        price_raw: int,
        paid_raw: int,
        link_as_account: str,
        representative: str,
        subtype: str,
        block_time: int | None = None,
        expires_at: int | None = None,
    ) -> CreditResult:
        """Validate one confirmed block against an order and claim it once.

        Every field is checked before anything is written; a block is credited
        only when it is a *send* of exactly ``price_raw`` to ``pay_to`` whose
        representative is this order's commitment. The write is one-shot: a
        re-read of the same block for the same order is idempotent, a different
        block for an already-credited order is a duplicate, and a block already
        claimed by another order is refused.
        """
        if subtype != "send":
            return CreditResult("refusable_not_payment")
        if not _hex64(block_hash):
            return CreditResult("inconclusive")
        if link_as_account != pay_to:
            return CreditResult("refusable_not_payment")
        if int(paid_raw) != int(price_raw):
            return CreditResult("refusable_wrong_amount")
        if representative != commitment_rep_account(order_id, pay_to, price_raw):
            return CreditResult("refusable_other_quote")
        if (
            expires_at is not None
            and block_time is not None
            and block_time > expires_at
        ):
            return CreditResult("refusable_late")
        with self._lock:
            try:
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO nano_claims VALUES(?,?,?,?)",
                        (block_hash, order_id, str(int(paid_raw)), block_time),
                    )
                return CreditResult("matched", order_id)
            except sqlite3.IntegrityError:
                same_block = self._conn.execute(
                    "SELECT order_id FROM nano_claims WHERE block_hash=?",
                    (block_hash,),
                ).fetchone()
                if same_block is not None:
                    if same_block[0] == order_id:
                        return CreditResult("matched", order_id)
                    return CreditResult("refusable_other_quote", same_block[0])
                # order_id already credited by a different block
                return CreditResult("duplicate_refund_due", order_id)


def _hex64(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False
