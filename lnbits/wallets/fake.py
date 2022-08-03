import asyncio
import hashlib
import random
from datetime import datetime
from os import getenv
from typing import AsyncGenerator, Dict, Optional

from environs import Env  # type: ignore
from loguru import logger

from lnbits.helpers import urlsafe_short_hash

from ..bolt11 import decode, encode
from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)

env = Env()
env.read_env()


class FakeWallet(Wallet):
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
    ) -> InvoiceResponse:
        # we set a default secret since FakeWallet is used for internal=True invoices
        # and the user might not have configured a secret yet
        secret = env.str("FAKE_WALLET_SECTRET", default="ToTheMoon1")
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
            data["description_hash"] = description_hash.decode("utf-8")
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
            and invoice.checking_id[6:] == data["privkey"][:6]  # type: ignore
        ):
            return PaymentResponse(True, invoice.payment_hash, 0)
        else:
            return PaymentResponse(
                ok=False, error_message="Only internal invoices can be used!"
            )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
