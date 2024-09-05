from typing import AsyncGenerator

from loguru import logger

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class VoidWallet(Wallet):

    async def cleanup(self):
        pass

    async def create_invoice(self, *_, **__) -> InvoiceResponse:
        return InvoiceResponse(
            ok=False, error_message="VoidWallet cannot create invoices."
        )

    async def status(self) -> StatusResponse:
        logger.warning("VoidWallet is active. Payments and invoices are disabled.")
        return StatusResponse(None, 0)

    async def pay_invoice(self, *_, **__) -> PaymentResponse:
        return PaymentResponse(
            ok=False, error_message="VoidWallet cannot pay invoices."
        )

    async def get_invoice_status(self, *_, **__) -> PaymentStatus:
        return PaymentPendingStatus()

    async def get_payment_status(self, *_, **__) -> PaymentStatus:
        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        yield ""
