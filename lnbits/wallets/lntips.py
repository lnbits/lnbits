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
    InvoiceResponseFailed,
    InvoiceResponseSuccess,
    PaymentResponse,
    PaymentResponseFailed,
    PaymentResponseSuccess,
    PaymentStatus,
    PaymentStatusMap,
    PaymentStatusPending,
    StatusResponse,
    Wallet,
)


class LnTipsWallet(Wallet):
    def __init__(self):
        if not settings.lntips_api_endpoint:
            raise ValueError(
                "cannot initialize LnTipsWallet: missing lntips_api_endpoint"
            )
        key = (
            settings.lntips_api_key
            or settings.lntips_admin_key
            or settings.lntips_invoice_key
        )
        if not key:
            raise ValueError(
                "cannot initialize LnTipsWallet: "
                "missing lntips_api_key or lntips_admin_key or lntips_invoice_key"
            )

        self.endpoint = self.normalize_endpoint(settings.lntips_api_endpoint)

        headers = {
            "Authorization": f"Basic {key}",
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=headers)

    @property
    def payment_status_map(self) -> PaymentStatusMap:
        return PaymentStatusMap(
            success=[True],
            failed=[False],
            pending=[None],
        )

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        r = await self.client.get("/api/v1/balance", timeout=40)
        try:
            data = r.json()
        except Exception:
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
        **kwargs,
    ) -> InvoiceResponse:
        data: Dict = {"amount": amount, "description_hash": "", "memo": memo or ""}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        elif unhashed_description:
            data["description_hash"] = hashlib.sha256(unhashed_description).hexdigest()

        r = await self.client.post(
            "/api/v1/createinvoice",
            json=data,
            timeout=40,
        )

        if r.is_error:
            try:
                data = r.json()
                error_message = data["message"]
            except Exception:
                error_message = r.text

            return InvoiceResponseFailed(error_message=error_message)

        data = r.json()
        return InvoiceResponseSuccess(
            checking_id=data["payment_hash"], payment_request=data["payment_request"]
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        r = await self.client.post(
            "/api/v1/payinvoice",
            json={"pay_req": bolt11},
            timeout=None,
        )
        if r.is_error:
            return PaymentResponseFailed(error_message=r.text)

        if "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except Exception:
                error_message = r.text
            return PaymentResponseFailed(fee_msat=0, error_message=error_message)

        data = r.json()["details"]
        return PaymentResponseSuccess(
            checking_id=data["payment_hash"],
            fee_msat=-data["fee"],
            preimage=data["preimage"],
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.client.post(
                f"/api/v1/invoicestatus/{checking_id}",
            )

            if r.is_error or len(r.text) == 0:
                raise Exception

            data = r.json()
            return self.payment_status(data["paid"])
        except Exception:
            return PaymentStatusPending()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.client.post(
                url=f"/api/v1/paymentstatus/{checking_id}",
            )

            if r.is_error:
                raise Exception
            data = r.json()
            status = data.get("paid")

            return self.payment_status(None if status is False else status)
        except Exception:
            return PaymentStatusPending()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        last_connected = None
        while True:
            url = "/api/v1/invoicestream"
            try:
                last_connected = time.time()
                async with self.client.stream("GET", url, timeout=None) as r:
                    async for line in r.aiter_lines():
                        try:
                            prefix = "data: "
                            if not line.startswith(prefix):
                                continue
                            data = line[len(prefix) :]  # sse parsing
                            inv = json.loads(data)
                            if not inv.get("payment_hash"):
                                continue
                        except Exception:
                            continue
                        yield inv["payment_hash"]
            except Exception:
                pass

            # do not sleep if the connection was active for more than 10s
            # since the backend is expected to drop the connection after 90s
            if last_connected is None or time.time() - last_connected < 10:
                logger.error(
                    f"lost connection to {self.endpoint}/api/v1/invoicestream, retrying"
                    " in 5 seconds"
                )
                await asyncio.sleep(5)
