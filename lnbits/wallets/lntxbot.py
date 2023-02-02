import asyncio
import hashlib
import json
from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class LntxbotWallet(Wallet):
    """https://github.com/fiatjaf/lntxbot/blob/master/api.go"""

    def __init__(self):
        endpoint = settings.lntxbot_api_endpoint
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint

        key = (
            settings.lntxbot_key
            or settings.lntxbot_admin_key
            or settings.lntxbot_invoice_key
        )
        self.auth = {"Authorization": f"Basic {key}"}

    async def status(self) -> StatusResponse:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.endpoint}/balance", headers=self.auth, timeout=40
            )
        try:
            data = r.json()
        except:
            return StatusResponse(
                f"Failed to connect to {self.endpoint}, got: '{r.text[:200]}...'", 0
            )

        if data.get("error"):
            return StatusResponse(data["message"], 0)

        return StatusResponse(None, data["BTC"]["AvailableBalance"] * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        data: Dict = {"amt": str(amount)}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        elif unhashed_description:
            data["description_hash"] = hashlib.sha256(unhashed_description).hexdigest()
        else:
            data["memo"] = memo or ""

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.endpoint}/addinvoice", headers=self.auth, json=data, timeout=40
            )

        if r.is_error:
            try:
                data = r.json()
                error_message = data["message"]
            except:
                error_message = r.text

            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        return InvoiceResponse(True, data["payment_hash"], data["pay_req"], None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.endpoint}/payinvoice",
                headers=self.auth,
                json={"invoice": bolt11},
                timeout=None,
            )

        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["message"]
            except:
                error_message = r.text
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()
        if data.get("type") != "paid_invoice":
            return PaymentResponse(None)
        checking_id = data["payment_hash"]
        fee_msat = -data["fee_msat"]
        preimage = data["payment_preimage"]
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.endpoint}/invoicestatus/{checking_id}?wait=false",
                headers=self.auth,
            )

        data = r.json()
        if r.is_error or "error" in data:
            return PaymentStatus(None)

        if "preimage" not in data:
            return PaymentStatus(False)

        return PaymentStatus(True)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url=f"{self.endpoint}/paymentstatus/{checking_id}", headers=self.auth
            )

        data = r.json()
        if r.is_error or "error" in data:
            return PaymentStatus(None)

        statuses = {"complete": True, "failed": False, "pending": None, "unknown": None}
        return PaymentStatus(statuses[data.get("status", "unknown")])

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        url = f"{self.endpoint}/payments/stream"

        while True:
            try:
                async with httpx.AsyncClient(timeout=None, headers=self.auth) as client:
                    async with client.stream("GET", url) as r:
                        async for line in r.aiter_lines():
                            if line.startswith("data:"):
                                data = json.loads(line[5:])
                                if "payment_hash" in data and data.get("msatoshi") > 0:
                                    yield data["payment_hash"]
            except (OSError, httpx.ReadError, httpx.ReadTimeout, httpx.ConnectError):
                pass

            logger.error(
                "lost connection to lntxbot /payments/stream, retrying in 5 seconds"
            )
            await asyncio.sleep(5)
