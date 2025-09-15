import asyncio
import json
import base64
from collections.abc import AsyncGenerator
from datetime import datetime
from hashlib import sha256
from os import urandom
from typing import Any

from loguru import logger

from lnbits.settings import settings
from lnbits.utils.crypto import fake_privkey  # kept for parity/log symmetry

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)

ARK_TICKET_PREFIX = "ark1"  # cosmetic prefix for readability


def _b64u_encode(d: dict[str, Any]) -> str:
    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64u_decode(s: str) -> dict[str, Any]:
    # Restore missing padding
    pad = "=" * (-len(s) % 4)
    raw = base64.urlsafe_b64decode(s + pad)
    return json.loads(raw.decode())


def encode_ark_ticket(payload: dict[str, Any]) -> str:
    return f"{ARK_TICKET_PREFIX}{_b64u_encode(payload)}"


def decode_ark_ticket(ticket: str) -> dict[str, Any]:
    if not ticket.startswith(ARK_TICKET_PREFIX):
        raise ValueError("Not an ARK ticket")
    return _b64u_decode(ticket[len(ARK_TICKET_PREFIX) :])


class ArkFakeWallet(Wallet):
    """
    A fake ARK funding source:
    - create_invoice() returns an ARK 'ticket' string in `payment_request`.
    - pay_invoice() accepts the ARK ticket string (only if it was created internally).
    - Status/streams mimic FakeWallet for compatibility in tests/dev.
    """

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue(0)
        self.payment_secrets: dict[str, str] = {}  # payment_hash -> preimage hex
        self.paid_invoices: set[str] = set()
        # keep these two to mirror FakeWallet’s behavior/logging vibe
        self.secret = settings.fake_wallet_secret
        self.privkey = fake_privkey(self.secret)

    async def cleanup(self):
        pass

    async def status(self) -> StatusResponse:
        logger.info(
            "ArkFakeWallet funding source is a local-only simulator for ARK tickets."
        )
        # second field is "balance" in some Wallet impls; keep it big & static
        return StatusResponse(None, 1_000_000_000)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        expiry: int | None = None,
        payment_secret: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        # For ARK we don’t use BOLT11 tags; we just build a ticket payload.
        if payment_secret:
            secret_hex = payment_secret.hex()
        else:
            secret_hex = urandom(32).hex()

        # In Lightning this would be the payment preimage; we keep the same idea.
        preimage = urandom(32)
        payment_hash = sha256(preimage).hexdigest()

        now = int(datetime.now().timestamp())
        ticket_payload = {
            "v": 1,  # version for future-proofing your decoder
            "ts": now,
            "amt_sat": int(amount),
            "memo": memo or "",
            "secret": secret_hex,
            "hash": payment_hash,  # used as checking_id
        }
        if expiry:
            ticket_payload["exp"] = int(expiry)

        ticket = encode_ark_ticket(ticket_payload)

        # Track so we can accept only internal tickets on pay
        self.payment_secrets[payment_hash] = preimage.hex()

        return InvoiceResponse(
            ok=True,
            checking_id=payment_hash,
            payment_request=ticket,  # <-- ARK ticket string goes here
            preimage=preimage.hex(),  # provided for symmetry with FakeWallet
        )

    async def pay_invoice(self, bolt11: str, _: int) -> PaymentResponse:
        """
        For ArkFakeWallet, `bolt11` is actually an ARK ticket string (ark1...).
        Only internal tickets are payable (just like FakeWallet).
        """
        try:
            ticket = decode_ark_ticket(bolt11)
        except Exception as exc:
            return PaymentResponse(ok=False, error_message=f"Invalid ARK ticket: {exc}")

        checking_id = ticket.get("hash")
        if not isinstance(checking_id, str):
            return PaymentResponse(ok=False, error_message="Malformed ARK ticket (no hash)")

        if checking_id in self.payment_secrets:
            # "Pay" it: mark as paid and enqueue for stream consumers
            await self.queue.put(checking_id)
            self.paid_invoices.add(checking_id)
            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=0,
                preimage=self.payment_secrets.get(checking_id) or "0" * 64,
            )
        else:
            return PaymentResponse(
                ok=False, error_message="Only internal ARK tickets can be used!"
            )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        if checking_id in self.paid_invoices:
            return PaymentSuccessStatus()
        if checking_id in self.payment_secrets:
            return PaymentPendingStatus()
        return PaymentFailedStatus()

    async def get_payment_status(self, _: str) -> PaymentStatus:
        # We don't track outgoing states beyond "we 'paid' it"
        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        # Mimic FakeWallet: stream checking_id/payment_hash values
        while settings.lnbits_running:
            checking_id = await self.queue.get()
            yield checking_id
