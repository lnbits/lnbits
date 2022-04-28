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
        secret = getenv("FAKE_WALLET_SECRET")
        data: Dict = {
            "out": False,
            "amount": amount,
            "currency": "bc",
            "privkey": hashlib.pbkdf2_hmac(
                "sha256",
                secret.encode("utf-8"),
                ("FakeWallet").encode("utf-8"),
                2048,
                32,
            ).hex(),
            "memo": None,
            "description_hash": None,
            "description": "",
            "fallback": None,
            "expires": None,
            "route": None,
        }
        data["amount"] = amount * 1000
        data["timestamp"] = datetime.now().timestamp()
        if description_hash:
            data["tags_set"] = ["h"]
            data["description_hash"] = description_hash.hex()
        else:
            data["tags_set"] = ["d"]
            data["memo"] = memo
            data["description"] = memo
        randomHash = (
            data["privkey"][:6]
            + hashlib.sha256(str(random.getrandbits(256)).encode("utf-8")).hexdigest()[
                6:
            ]
        )
        data["paymenthash"] = randomHash
        payment_request = encode(data)
        checking_id = randomHash

        return InvoiceResponse(True, checking_id, payment_request)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        invoice = decode(bolt11)
        if (
            hasattr(invoice, "checking_id")
            and invoice.checking_id[6:] == data["privkey"][:6]
        ):
            return PaymentResponse(True, invoice.payment_hash, 0)
        else:
            return PaymentResponse(
                ok=False, error_message="Only internal invoices can be used!"
            )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(False)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(False)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
