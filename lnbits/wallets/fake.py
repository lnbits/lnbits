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
from ..bolt11 import encode
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
        self.description_hashed = ""
        self.description = ""
        self.fallback = None
        self.expires = None
        self.route = None
    async def status(self) -> StatusResponse:
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
        print(self.privkey)
        self.amount = amount
        self.timestamp = datetime.now().timestamp()
        if description_hash:
            self.tags_set = {"h"}
            self.description_hashed = description_hash
        else:
            self.tags_set = {"d"}
            self.memo = memo
            self.description = memo
        letters = string.ascii_lowercase
        randomHash = hashlib.sha256(str(random.getrandbits(256)).encode('utf-8')).hexdigest()
        self.paymenthash = randomHash
        payment_request = encode(self)
        print(payment_request)
        checking_id = randomHash

        return InvoiceResponse(True, checking_id, payment_request)


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
