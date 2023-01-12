import asyncio
import hashlib
import json
import time
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


class LnTipsWallet(Wallet):
    def __init__(self):
        endpoint = settings.lntips_api_endpoint
        key = (
            settings.lntips_api_key
            or settings.lntips_admin_key
            or settings.lntips_invoice_key
        )
        if not endpoint or not key:
            raise Exception("cannot initialize lntxbod")
        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth = {"Authorization": f"Basic {key}"}

    async def status(self) -> StatusResponse:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.endpoint}/api/v1/balance", headers=self.auth, timeout=40
            )
        try:
            data = r.json()
        except:
            return StatusResponse(
                f"Failed to connect to {self.endpoint}, got: '{r.text[:200]}...'", 0
            )

        if data.get("error"):
            return StatusResponse(data["error"], 0)

        return StatusResponse(None, data["balance"] * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
    ) -> InvoiceResponse:
        data: Dict = {"amount": amount, "description_hash": "", "memo": memo or ""}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        elif unhashed_description:
            data["description_hash"] = hashlib.sha256(unhashed_description).hexdigest()

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.endpoint}/api/v1/createinvoice",
                headers=self.auth,
                json=data,
                timeout=40,
            )

        if r.is_error:
            try:
                data = r.json()
                error_message = data["message"]
            except:
                error_message = r.text

            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        return InvoiceResponse(
            True, data["payment_hash"], data["payment_request"], None
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.endpoint}/api/v1/payinvoice",
                headers=self.auth,
                json={"pay_req": bolt11},
                timeout=None,
            )
        if r.is_error:
            return PaymentResponse(False, None, 0, None, r.text)

        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except:
                error_message = r.text
            return PaymentResponse(False, None, 0, None, error_message)

        data = r.json()["details"]
        checking_id = data["payment_hash"]
        fee_msat = -data["fee"]
        preimage = data["preimage"]
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.endpoint}/api/v1/invoicestatus/{checking_id}",
                    headers=self.auth,
                )

            if r.is_error or len(r.text) == 0:
                raise Exception

            data = r.json()
            return PaymentStatus(data["paid"])
        except:
            return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    url=f"{self.endpoint}/api/v1/paymentstatus/{checking_id}",
                    headers=self.auth,
                )

            if r.is_error:
                raise Exception
            data = r.json()

            paid_to_status = {False: None, True: True}
            return PaymentStatus(paid_to_status[data.get("paid")])
        except:
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        last_connected = None
        while True:
            url = f"{self.endpoint}/api/v1/invoicestream"
            try:
                async with httpx.AsyncClient(timeout=None, headers=self.auth) as client:
                    last_connected = time.time()
                    async with client.stream("GET", url) as r:
                        async for line in r.aiter_lines():
                            try:
                                prefix = "data: "
                                if not line.startswith(prefix):
                                    continue
                                data = line[len(prefix) :]  # sse parsing
                                inv = json.loads(data)
                                if not inv.get("payment_hash"):
                                    continue
                            except:
                                continue
                            yield inv["payment_hash"]
            except Exception:
                pass

            # do not sleep if the connection was active for more than 10s
            # since the backend is expected to drop the connection after 90s
            if last_connected is None or time.time() - last_connected < 10:
                logger.error(
                    f"lost connection to {self.endpoint}/api/v1/invoicestream, retrying in 5 seconds"
                )
                await asyncio.sleep(5)
