import asyncio
import json
import httpx
from os import getenv
from datetime import datetime, timedelta
from typing import Optional, Dict, AsyncGenerator
import random
import string
from lnbits.helpers import urlsafe_short_hash
import hashlib
from ..bolt11 import encode, decode
from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
)

class FakeWallet(Wallet):
    def __init__(self):
        self.amount = 0
        self.timestamp = 0
        self.currency = "bc"
        self.paymenthash = ""
        self.privkey = getenv("FAKE_WALLET_KEY")
        self.memo = ""
        self.description_hash = ""
        self.description = ""
        self.fallback = None
        self.expires = None
        self.route = None

    async def status(self) -> StatusResponse:
        print(
            "FakeWallet funding source is for using LNbits as a centralised, stand-alone payment system with brrrrrr."
        )
        return StatusResponse(None, float("inf"))

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:

        self.amount = amount
        self.timestamp = datetime.now().timestamp()
        if description_hash:
            self.tags_set = {"h"}
            self.description_hash = description_hash.hex()
        else:
            self.tags_set = {"d"}
            self.memo = memo
            self.description = memo
        letters = string.ascii_lowercase
        randomHash = hashlib.sha256(
            str(random.getrandbits(256)).encode("utf-8")
        ).hexdigest()
        self.paymenthash = randomHash
        payment_request = encode(self)
        print(payment_request)
        checking_id = randomHash

        return InvoiceResponse(True, checking_id, payment_request)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:
        invoice = decode(bolt11)
        return PaymentResponse(True, invoice.payment_hash, 0)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(False)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(False)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
