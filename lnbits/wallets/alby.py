import asyncio
import hashlib
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


class AlbyWallet(Wallet):
    """https://guides.getalby.com/alby-wallet-api/reference/api-reference"""

    def __init__(self):
        if not settings.alby_api_endpoint:
            raise ValueError("cannot initialize AlbyWallet: missing alby_api_endpoint")
        if not settings.alby_access_token:
            raise ValueError("cannot initialize AlbyWallet: missing alby_access_token")

        self.endpoint = self.normalize_endpoint(settings.alby_api_endpoint)
        self.auth = {
            "Authorization": "Bearer " + settings.alby_access_token,
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.auth)

    @property
    def payment_status_map(self) -> PaymentStatusMap:
        return PaymentStatusMap(
            success=["SETTLED"],
            failed=[],
            pending=["CREATED"],
        )

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get("/balance", timeout=10)
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse(f"Unable to connect to '{self.endpoint}'", 0)

        if r.is_error:
            error_message = r.json()["message"]
            return StatusResponse(error_message, 0)

        data = r.json()
        assert data["unit"] == "sat"
        # multiply balance by 1000 to get msats balance
        return StatusResponse(None, data["balance"] * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        # https://api.getalby.com/invoices
        data: Dict = {"amount": f"{amount}"}
        if description_hash:
            data["description_hash"] = description_hash.hex()
        elif unhashed_description:
            data["description_hash"] = hashlib.sha256(unhashed_description).hexdigest()
        else:
            data["memo"] = memo or ""

        r = await self.client.post(
            "/invoices",
            json=data,
            timeout=40,
        )

        if r.is_error:
            return InvoiceResponseFailed(error_message=r.json()["message"])

        data = r.json()
        return InvoiceResponseSuccess(
            checking_id=data["payment_hash"], payment_request=data["payment_request"]
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        # https://api.getalby.com/payments/bolt11
        r = await self.client.post(
            "/payments/bolt11",
            json={"invoice": bolt11},  # assume never need amount in body
            timeout=None,
        )

        if r.is_error:
            error_message = r.json()["message"]
            return PaymentResponseFailed(error_message=error_message)

        data = r.json()
        checking_id = data["payment_hash"]
        fee_msat = -data["fee"]
        preimage = data["payment_preimage"]

        return PaymentResponseSuccess(checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return await self.get_payment_status(checking_id)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(f"/invoices/{checking_id}")

        if r.is_error:
            return PaymentStatusPending()

        data = r.json()

        return self.payment_status(data.get("state"))

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
