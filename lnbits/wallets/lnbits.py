import asyncio
import json
from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger

from lnbits.settings import settings

from ..core.models import Payment, PaymentStatus
from .base import InvoiceResponse, PaymentResponse, StatusResponse, Wallet


class LNbitsWallet(Wallet):
    """https://github.com/lnbits/lnbits"""

    def __init__(self):
        self.endpoint = settings.lnbits_endpoint
        key = (
            settings.lnbits_key
            or settings.lnbits_admin_key
            or settings.lnbits_invoice_key
        )
        if not self.endpoint or not key:
            raise Exception("cannot initialize lnbits wallet")
        self.key = {"X-Api-Key": key}
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.key)

    async def cleanup(self):
        await self.client.aclose()

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get(url="/api/v1/wallet", timeout=15)
        except Exception as exc:
            return StatusResponse(
                f"Failed to connect to {self.endpoint} due to: {exc}", 0
            )

        try:
            data = r.json()
        except:
            return StatusResponse(
                f"Failed to connect to {self.endpoint}, got: '{r.text[:200]}...'", 0
            )

        if r.is_error:
            return StatusResponse(data["detail"], 0)

        return StatusResponse(None, data["balance"])

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        data: Dict = {"out": False, "amount": amount, "memo": memo or ""}
        if kwargs.get("expiry"):
            data["expiry"] = kwargs["expiry"]
        if description_hash:
            data["description_hash"] = description_hash.hex()
        if unhashed_description:
            data["unhashed_description"] = unhashed_description.hex()

        r = await self.client.post(url="/api/v1/payments", json=data)
        ok, checking_id, payment_request, error_message = (
            not r.is_error,
            None,
            None,
            None,
        )

        if r.is_error:
            error_message = r.json()["detail"]
        else:
            data = r.json()
            checking_id, payment_request = data["checking_id"], data["payment_request"]

        return InvoiceResponse(ok, checking_id, payment_request, error_message)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        r = await self.client.post(
            url="/api/v1/payments",
            json={"out": True, "bolt11": bolt11},
            timeout=None,
        )
        ok = not r.is_error

        if r.is_error:
            error_message = r.json()["detail"]
            return PaymentResponse(None, None, None, None, error_message)
        else:
            data = r.json()
            checking_id = data["payment_hash"]

        # we do this to get the fee and preimage
        payment: PaymentStatus = await self.get_payment_status(checking_id)

        return PaymentResponse(ok, checking_id, payment.fee_msat, payment.preimage)

    async def get_invoice_status(self, payment: Payment) -> PaymentStatus:
        try:
            r = await self.client.get(
                url=f"/api/v1/payments/{payment.checking_id}",
            )
            if r.is_error:
                return PaymentStatus(None)
            return PaymentStatus(r.json()["paid"])
        except:
            return PaymentStatus(None)

    async def get_payment_status(self, payment: Payment) -> PaymentStatus:
        r = await self.client.get(url=f"/api/v1/payments/{payment.checking_id}")

        if r.is_error:
            return PaymentStatus(None)
        data = r.json()
        if "paid" not in data and "details" not in data:
            return PaymentStatus(None)

        return PaymentStatus(data["paid"], data["details"]["fee"], data["preimage"])

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        url = f"{self.endpoint}/api/v1/payments/sse"

        while True:
            try:
                async with httpx.AsyncClient(timeout=None, headers=self.key) as client:
                    del client.headers[
                        "accept-encoding"
                    ]  # we have to disable compression for SSEs
                    async with client.stream(
                        "GET", url, content="text/event-stream"
                    ) as r:
                        sse_trigger = False
                        async for line in r.aiter_lines():
                            # The data we want to listen to is of this shape:
                            # event: payment-received
                            # data: {.., "payment_hash" : "asd"}
                            if line.startswith("event: payment-received"):
                                sse_trigger = True
                                continue
                            elif sse_trigger and line.startswith("data:"):
                                data = json.loads(line[len("data:") :])
                                sse_trigger = False
                                yield data["payment_hash"]
                            else:
                                sse_trigger = False

            except (OSError, httpx.ReadError, httpx.ConnectError, httpx.ReadTimeout):
                pass

            logger.error(
                "lost connection to lnbits /payments/sse, retrying in 5 seconds"
            )
            await asyncio.sleep(5)
