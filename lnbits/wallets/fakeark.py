# lnbits/wallets/ark_fake.py
import asyncio, json, base64
from collections.abc import AsyncGenerator
from datetime import datetime
from hashlib import sha256
from os import urandom
from typing import Any

from loguru import logger
from lnbits.settings import settings
from lnbits.utils.crypto import fake_privkey  # unused but kept for parity/logs

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

def ark_encode(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    return "ark1" + base64.urlsafe_b64encode(raw).decode().rstrip("=")

class ArkFakeWallet(Wallet):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue(0)
        self.payment_secrets: dict[str, str] = {}
        self.paid_invoices: set[str] = set()
        self.secret = settings.fake_wallet_secret
        self.privkey = fake_privkey(self.secret)

    async def cleanup(self): pass

    async def status(self) -> StatusResponse:
        logger.info("ArkFakeWallet: ARK-only test funding source (no bolt11).")
        return StatusResponse(None, 1_000_000_000)

    async def create_invoice(
        self, amount: int, memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        expiry: int | None = None,
        payment_secret: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        preimage = urandom(32)
        p_hash = sha256(preimage).hexdigest()
        now = int(datetime.now().timestamp())
        ticket = ark_encode({
            "v": 1,
            "ts": now,
            "amt_sat": int(amount),
            "memo": memo or "",
            "hash": p_hash,
            "exp": int(expiry or 3600),
            "secret": (payment_secret.hex() if payment_secret else urandom(32).hex()),
        })
        self.payment_secrets[p_hash] = preimage.hex()
        return InvoiceResponse(
            ok=True,
            checking_id=p_hash,
            payment_request=ticket,   # <-- non-bolt11, starts with ark1
            preimage=preimage.hex(),
        )

    async def pay_invoice(self, bolt11: str, _: int) -> PaymentResponse:
        # Only allow paying our own tickets (like FakeWallet behavior)
        # We don’t parse here because we only care about internal payments.
        # If you want to parse/validate, you can mirror the core’s ark parser.
        for p_hash in list(self.payment_secrets.keys()):
            if p_hash in bolt11:  # cheap check; or properly decode ark1 and compare its "hash"
                await self.queue.put(p_hash)
                self.paid_invoices.add(p_hash)
                return PaymentResponse(
                    ok=True,
                    checking_id=p_hash,
                    fee_msat=0,
                    preimage=self.payment_secrets[p_hash],
                )
        return PaymentResponse(ok=False, error_message="Only internal ARK tickets can be used!")

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        if checking_id in self.paid_invoices:
            return PaymentSuccessStatus()
        if checking_id in self.payment_secrets:
            return PaymentPendingStatus()
        return PaymentFailedStatus()

    async def get_payment_status(self, _: str) -> PaymentStatus:
        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            checking_id = await self.queue.get()
            yield checking_id
