import asyncio
import base64
import hashlib
import json
import urllib.parse
from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger
from websockets.client import connect

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class EclairError(Exception):
    pass


class UnknownError(Exception):
    pass


class EclairWallet(Wallet):
    def __init__(self):
        url = settings.eclair_url
        passw = settings.eclair_pass
        if not url or not passw:
            raise Exception("cannot initialize eclair")

        self.url = url[:-1] if url.endswith("/") else url
        self.ws_url = f"ws://{urllib.parse.urlsplit(self.url).netloc}/ws"

        encodedAuth = base64.b64encode(f":{passw}".encode())
        auth = str(encodedAuth, "utf-8")
        self.auth = {"Authorization": f"Basic {auth}"}

    async def status(self) -> StatusResponse:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/globalbalance", headers=self.auth, timeout=5
            )
        try:
            data = r.json()
        except:
            return StatusResponse(
                f"Failed to connect to {self.url}, got: '{r.text[:200]}...'", 0
            )

        if r.is_error:
            return StatusResponse(data.get("error") or "undefined error", 0)
        if len(data) == 0:
            return StatusResponse("no data", 0)

        return StatusResponse(None, int(data.get("total") * 100_000_000_000))

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        data: Dict = {
            "amountMsat": amount * 1000,
            "description_hash": b"",
            "description": memo,
        }
        if kwargs.get("expiry"):
            data["expireIn"] = kwargs["expiry"]

        if description_hash:
            data["descriptionHash"] = description_hash.hex()
        elif unhashed_description:
            data["descriptionHash"] = hashlib.sha256(unhashed_description).hexdigest()

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/createinvoice", headers=self.auth, data=data, timeout=40
            )

        if r.is_error:
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text

            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        return InvoiceResponse(True, data["paymentHash"], data["serialized"], None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/payinvoice",
                headers=self.auth,
                data={"invoice": bolt11, "blocking": True},
                timeout=None,
            )

        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()

        if data["type"] == "payment-failed":
            return PaymentResponse(False, None, None, None, "payment failed")

        checking_id = data["paymentHash"]
        preimage = data["paymentPreimage"]

        # We do all this again to get the fee:

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/getsentinfo",
                headers=self.auth,
                data={"paymentHash": checking_id},
                timeout=40,
            )

        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text
            return PaymentResponse(None, checking_id, None, preimage, error_message)

        statuses = {
            "sent": True,
            "failed": False,
            "pending": None,
        }

        data = r.json()[-1]
        fee_msat = 0
        if data["status"]["type"] == "sent":
            fee_msat = -data["status"]["feesPaid"]
            preimage = data["status"]["paymentPreimage"]

        return PaymentResponse(
            statuses[data["status"]["type"]], checking_id, fee_msat, preimage, None
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.url}/getreceivedinfo",
                    headers=self.auth,
                    data={"paymentHash": checking_id},
                )

            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or data.get("status") is None:
                raise Exception("error in eclair response")

            statuses = {
                "received": True,
                "expired": False,
                "pending": None,
            }
            return PaymentStatus(statuses.get(data["status"]["type"]))
        except:
            return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.url}/getsentinfo",
                    headers=self.auth,
                    data={"paymentHash": checking_id},
                    timeout=40,
                )

            r.raise_for_status()

            data = r.json()[-1]

            if r.is_error or "error" in data or data.get("status") is None:
                raise Exception("error in eclair response")

            fee_msat, preimage = None, None
            if data["status"]["type"] == "sent":
                fee_msat = -data["status"]["feesPaid"]
                preimage = data["status"]["paymentPreimage"]

            statuses = {
                "sent": True,
                "failed": False,
                "pending": None,
            }
            return PaymentStatus(
                statuses.get(data["status"]["type"]), fee_msat, preimage
            )
        except:
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                async with connect(
                    self.ws_url,
                    extra_headers=[("Authorization", self.auth["Authorization"])],
                ) as ws:
                    while True:
                        message = await ws.recv()
                        message_json = json.loads(message)

                        if message_json and message_json["type"] == "payment-received":
                            yield message_json["paymentHash"]

            except Exception as exc:
                logger.error(
                    f"lost connection to eclair invoices stream: '{exc}', retrying in 5 seconds"
                )
                await asyncio.sleep(5)
