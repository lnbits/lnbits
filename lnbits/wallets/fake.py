import asyncio
import json
import httpx
from os import getenv
from datetime import datetime, timedelta
from typing import Optional, Dict, AsyncGenerator
import hashlib
from ..bolt11 import encode
from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
)

class FakeWallet(Wallet):
    """https://github.com/lnbits/lnbits"""

        print(
            "The FakeWallet backend is for using LNbits as a centralised, stand-alone payment system."
        )
        return StatusResponse(None, 21000000000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        class options:
            def __init__(self, amount, timestamp, payments_hash, privkey, memo, ):
                self.name = name
                self.age = age
                async def status(self) -> StatusResponse:
        
        randomHash = hashlib.sha256(b"some random data").hexdigest()
        options = {
            "amount": amount,
            "timestamp": datetime.now().timestamp(),
            "payments_hash": randomHash,
            "privkey": "v3qrevqrevm39qin0vq3r0ivmrewvmq3rimq03ig",
            "memo": "",
            "description_hashed": "",
        }
        if description_hash:
            options.description_hashed = description_hash
        else:
            options.memo = memo
        payment_request = encode(options)
        print(payment_request)
        checking_id = randomHash

        return InvoiceResponse(ok, checking_id, payment_request)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:

        return ""

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:

        return ""

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:

        return ""

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        yield ""


# invoice = "lnbc"
# invoice += str(data.amount) + "m1"
# invoice += str(datetime.now().timestamp()).to_bytes(35, byteorder='big'))
# invoice += str(hashlib.sha256(b"some random data").hexdigest()) # hash of preimage, can be fake as invoice handled internally
# invoice += "dpl" # d then pl (p = 1, l = 31; 1 * 32 + 31 == 63)
# invoice += "2pkx2ctnv5sxxmmwwd5kgetjypeh2ursdae8g6twvus8g6rfwvs8qun0dfjkxaq" #description, how do I encode this?
# invoice += str(hashlib.sha224("lnbc" + str(data.amount) + "m1").hexdigest())
