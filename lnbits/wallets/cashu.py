import asyncio
from typing import AsyncGenerator, Optional

import httpx

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class CashuWallet(Wallet):
    def __init__(self):
        if not settings.cashu_wallet_endpoint:
            raise ValueError(
                "cannot initialize CashuWallet: missing cashu_wallet_endpoint"
            )

        self.endpoint = self.normalize_endpoint(settings.cashu_wallet_endpoint)
        self.client = httpx.AsyncClient(base_url=self.endpoint)

        # run async_init avoiding the following error:
        # asyncio.run() cannot be called from a running event loop

    async def cleanup(self):
        pass
        # try:
        #     await self.client.aclose()
        # except RuntimeError as e:
        #     logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get("/lightning/balance")
            r.raise_for_status()
        except (httpx.ConnectError, httpx.RequestError) as exc:
            return StatusResponse(f"Unable to connect to {self.endpoint}. {exc}", 0)
        status = StatusResponse(**r.json())
        return status

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        r = await self.client.post(
            "/lightning/create_invoice", params={"amount": amount}
        )
        r.raise_for_status()
        return InvoiceResponse(**r.json())

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        r = await self.client.post(
            "/lightning/pay_invoice", params={"bolt11": bolt11}, timeout=None
        )
        r.raise_for_status()
        return PaymentResponse(**r.json())

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(
            "/lightning/invoice_state", params={"payment_hash": checking_id}
        )
        r.raise_for_status()
        return PaymentStatus(**r.json())

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(
            "/lightning/payment_state", params={"id": checking_id}
        )
        r.raise_for_status()
        return PaymentStatus(**r.json())

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
