from typing import Optional

from .base import InvoiceResponse, PaymentResponse, PaymentStatus, Wallet, Unsupported


class VoidWallet(Wallet):
    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        raise Unsupported("")

    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        raise Unsupported("")

    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        raise Unsupported("")

    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        raise Unsupported("")
