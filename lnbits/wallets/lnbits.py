import asyncio
import hashlib
import json
from os import getenv
from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class LNbitsWallet(Wallet):
    """https://github.com/lnbits/lnbits"""

    def __init__(self):
        self.endpoint = getenv("LNBITS_ENDPOINT")

        key = (
            getenv("LNBITS_KEY")
            or getenv("LNBITS_ADMIN_KEY")
            or getenv("LNBITS_INVOICE_KEY")
        )
        self.key = {"X-Api-Key": key}

    async def status(self) -> StatusResponse:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    url=f"{self.endpoint}/api/v1/wallet", headers=self.key, timeout=15
                )
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
    ) -> InvoiceResponse:
        data: Dict = {"out": False, "amount": amount}
        if description_hash:
            data["description_hash"] = hashlib.sha256(description_hash).hexdigest()
        else:
            data["memo"] = memo or ""

        async with httpx.AsyncClient() as client:
            r = await client.post(
                url=f"{self.endpoint}/api/v1/payments", headers=self.key, json=data
            )
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
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url=f"{self.endpoint}/api/v1/payments",
                headers=self.key,
                json={"out": True, "bolt11": bolt11},
                timeout=None,
            )
        ok, checking_id, fee_msat, error_message = not r.is_error, None, 0, None

        if r.is_error:
            error_message = r.json()["detail"]
        else:
            data = r.json()
            checking_id = data["checking_id"]

        return PaymentResponse(ok, checking_id, fee_msat, error_message)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    url=f"{self.endpoint}/api/v1/payments/{checking_id}",
                    headers=self.key,
                )
            if r.is_error:
                return PaymentStatus(None)
            return PaymentStatus(r.json()["paid"])
        except:
            return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                url=f"{self.endpoint}/api/v1/payments/{checking_id}", headers=self.key
            )

        if r.is_error:
            return PaymentStatus(None)

        return PaymentStatus(r.json()["paid"])

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        url = f"{self.endpoint}/api/v1/payments/sse"

        while True:
            try:
                async with httpx.AsyncClient(timeout=None, headers=self.key) as client:
                    async with client.stream("GET", url) as r:
                        async for line in r.aiter_lines():
                            if line.startswith("data:"):
                                try:
                                    data = json.loads(line[5:])
                                except json.decoder.JSONDecodeError:
                                    continue

                                if type(data) is not dict:
                                    continue

                                yield data["payment_hash"]  # payment_hash

            except (OSError, httpx.ReadError, httpx.ConnectError, httpx.ReadTimeout):
                pass

            logger.error(
                "lost connection to lnbits /payments/sse, retrying in 5 seconds"
            )
            await asyncio.sleep(5)
