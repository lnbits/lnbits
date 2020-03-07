from abc import ABC, abstractmethod
from requests import Response
from typing import NamedTuple, Optional


class InvoiceResponse(NamedTuple):
    raw_response: Response
    payment_hash: Optional[str] = None
    payment_request: Optional[str] = None


class PaymentResponse(NamedTuple):
    raw_response: Response
    failed: bool = False
    fee_msat: int = 0
    error_message: Optional[str] = None


class PaymentStatus(NamedTuple):
    raw_response: Response
    paid: Optional[bool] = None

    @property
    def pending(self) -> bool:
        return self.paid is not True


class Wallet(ABC):
    @abstractmethod
    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        pass

    @abstractmethod
    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        pass

    @abstractmethod
    def get_invoice_status(self, payment_hash: str) -> PaymentStatus:
        pass

    @abstractmethod
    def get_payment_status(self, payment_hash: str) -> PaymentStatus:
        pass
