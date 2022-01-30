import asyncio
import json
import httpx
from os import getenv
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
    async def status(self) -> StatusResponse:
        print("This backend does nothing, it is here just as a placeholder, you must configure an actual backend before being able to do anything useful with LNbits.")
        return StatusResponse(
            None,
            21000000000,
        )
    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:

        options.amount = amount
        options.timestamp = datetime.now().timestamp()
        randomHash = hashlib.sha256(b"some random data").hexdigest()
        options.payments_hash = hex(randomHash)
        options.privkey = "v3qrevqrevm39qin0vq3r0ivmrewvmq3rimq03ig"
        if description_hash:
            options.description_hashed = description_hash
        else:
            options.memo = memo
        payment_request = encode(options)
        checking_id = randomHash

        return InvoiceResponse(ok, checking_id, payment_request)

    async def pay_invoice(self, bolt11: str) -> PaymentResponse:


        return ""

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:

            return ""

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:


        return ""

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        url = f"{self.endpoint}/api/v1/payments/sse"
        print("lost connection to lnbits /payments/sse, retrying in 5 seconds")
        await asyncio.sleep(5)


#invoice = "lnbc"
#invoice += str(data.amount) + "m1"
#invoice += str(datetime.now().timestamp()).to_bytes(35, byteorder='big'))
#invoice += str(hashlib.sha256(b"some random data").hexdigest()) # hash of preimage, can be fake as invoice handled internally
#invoice += "dpl" # d then pl (p = 1, l = 31; 1 * 32 + 31 == 63)
#invoice += "2pkx2ctnv5sxxmmwwd5kgetjypeh2ursdae8g6twvus8g6rfwvs8qun0dfjkxaq" #description, how do I encode this?
#invoice += str(hashlib.sha224("lnbc" + str(data.amount) + "m1").hexdigest())
