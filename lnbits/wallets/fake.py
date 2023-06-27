import asyncio
import hashlib
import random
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional

from loguru import logger

from lnbits.settings import settings

from ..bolt11 import Invoice, decode, encode
from ..core.models import Payment
from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class FakeWallet(Wallet):
    queue: asyncio.Queue = asyncio.Queue(0)
    secret: str = settings.fake_wallet_secret
    privkey: str = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode(),
        ("FakeWallet").encode(),
        2048,
        32,
    ).hex()

    async def status(self) -> StatusResponse:
        logger.info(
            "FakeWallet funding source is for using LNbits as a centralised, stand-alone payment system with brrrrrr."
        )
        return StatusResponse(None, 1000000000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        data: Dict = {
            "out": False,
            "amount": amount * 1000,
            "currency": "bc",
            "privkey": self.privkey,
            "memo": memo,
            "description_hash": b"",
            "description": "",
            "fallback": None,
            "expires": kwargs.get("expiry"),
            "timestamp": datetime.now().timestamp(),
            "route": None,
            "tags_set": [],
        }
        if description_hash:
            data["tags_set"] = ["h"]
            data["description_hash"] = description_hash
        elif unhashed_description:
            data["tags_set"] = ["d"]
            data["description_hash"] = hashlib.sha256(unhashed_description).digest()
        else:
            data["tags_set"] = ["d"]
            data["memo"] = memo
            data["description"] = memo
        randomHash = (
            self.privkey[:6]
            + hashlib.sha256(str(random.getrandbits(256)).encode()).hexdigest()[6:]
        )
        data["paymenthash"] = randomHash
        payment_request = encode(data)
        checking_id = randomHash

        return InvoiceResponse(True, checking_id, payment_request)

    async def pay_invoice(self, bolt11: str, _: int) -> PaymentResponse:
        invoice = decode(bolt11)

        if invoice.payment_hash[:6] == self.privkey[:6]:
            await self.queue.put(invoice)
            return PaymentResponse(True, invoice.payment_hash, 0)
        else:
            return PaymentResponse(
                ok=False, error_message="Only internal invoices can be used!"
            )

    async def get_invoice_status(self, _: Payment) -> PaymentStatus:
        return PaymentStatus(None)

    async def get_payment_status(self, _: Payment) -> PaymentStatus:
        return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            value: Invoice = await self.queue.get()
            yield value.payment_hash
