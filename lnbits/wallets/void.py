from typing import Optional, AsyncGenerator

from .base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
    Unsupported,
)


class VoidWallet(Wallet):
    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> InvoiceResponse:
        raise Unsupported("")

    async def status(self) -> StatusResponse:
        print("This backend does nothing, it is here just as a placeholder, you must configure an actual backend before being able to do anything useful with LNbits.")
        return StatusResponse(None, 0)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        raise Unsupported("")

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        raise Unsupported("")

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        raise Unsupported("")

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        yield ""
