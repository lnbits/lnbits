import asyncio
from typing import AsyncGenerator, Optional

import httpx
from loguru import logger

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Unsupported,
    Wallet,
)


class AlbyWallet(Wallet):
    """https://guides.getalby.com/alby-wallet-api/reference/api-reference"""

    def __init__(self):
        endpoint = settings.alby_api_endpoint

        if not endpoint or not settings.alby_api_key:
            raise Exception("cannot initialize getalby")

        self.endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        self.auth = {"Authorization": "Bearer " + settings.alby_api_key}
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.auth)
        # print(f'Method __init__, endpoint : {endpoint}')
        # print(f'auth: {self.auth}')

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

        # print(f'Method Status:  {str(r.json())}')
        data = r.json()["balance"]
        if r.is_error:
            return StatusResponse(data["error"], 0)

        return StatusResponse(None, data)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        if description_hash or unhashed_description:
            raise Unsupported("description_hash")

        r = await self.client.post(
            "/invoices",
            json={
                "amount": amount,
                "description": memo or "",
            },
            timeout=40,
        )

        # print(f'method create_invoice, json : {r.json()}')

        if r.is_error:
            error_message = r.json()["message"]
            return InvoiceResponse(False, None, None, error_message)

        # data = r.json()["data"]
        data = r.json()
        checking_id = data["payment_hash"]
        payment_request = data["payment_request"]
        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        # https://api.getalby.com/payments/bolt11
        r = await self.client.post(
            "/payments/bolt11",
            json={"invoice": bolt11},  # assume never need amount in body
            timeout=None,
        )

        # print(f'Method pay_invoice, json : {r.json()}')
        if r.is_error:
            error_message = r.json()["message"]
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()
        checking_id = data["payment_hash"]
        fee_msat = -data["fee"]
        preimage = data["payment_preimage"]

        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return await self.get_payment_status(checking_id)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        # Note from API: currently only settled Alby invoices can be retrieved.
        r = await self.client.get(f"/invoices/{checking_id}")

        if r.is_error:
            return PaymentStatus(None)

        data = r.json()
        # print(f'method: get_payment_status: {data}')

        statuses = {
            "CREATED": None,
            "SETTLED": True,
            "error": None,
            "failed": False,
        }
        return PaymentStatus(statuses[data.get("state")], fee_msat=None, preimage=None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value

    async def webhook_listener(self):
        logger.error("Alby webhook listener disabled")
        return
