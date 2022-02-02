import asyncio
import hashlib
import random
from datetime import datetime
from os import getenv
from typing import AsyncGenerator, Dict, Optional

import lnbits.settings

from ..bolt11 import decode, encode
from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
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
        data: Dict = {
            "out": False,
            "amount": amount,
            "currency": "bc",
            "privkey": getenv("FAKE_WALLET_KEY"),
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
        randomHash = hashlib.sha256(
            str(random.getrandbits(256)).encode("utf-8")
        ).hexdigest()
        data["paymenthash"] = randomHash
        payment_request = encode(data)
        checking_id = f"{lnbits.settings.CLOSE_WALLET_TOKEN_ID}_{randomHash}"
        
        return InvoiceResponse(True, checking_id, payment_request)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:
        invoice = decode(bolt11)        
        if hasattr(invoice, 'checking_id') and invoice.checking_id.rsplit("_", 1)[0] == f"{lnbits.settings.CLOSE_WALLET_TOKEN_ID}":
            return PaymentResponse(True, invoice.payment_hash, 0)
        else:
            print("Only internal wallet invoices can be used!")
            return PaymentResponse(ok = False, error_message="Only internal wallet invoices can be used!")

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(False)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(False)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
