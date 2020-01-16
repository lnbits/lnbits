from abc import ABC, abstractmethod
from requests import Response
from typing import NamedTuple, Optional


class InvoiceResponse(NamedTuple):
    raw_response: Response
    payment_hash: Optional[str] = None
    payment_request: Optional[str] = None


class TxStatus(NamedTuple):
    raw_response: Response
    settled: Optional[bool] = None
    
class PaymentResponse(NamedTuple):
    raw_response: Response


class Wallet(ABC):
    @abstractmethod
    def create_invoice(self, amount: int, memo: str = "") -> InvoiceResponse:
        pass

    @abstractmethod
    def pay_invoice(self, bolt11: str) -> Response:
        pass

    @abstractmethod
    def get_invoice_status(self, payment_hash: str, wait: bool = True) -> TxStatus:
        pass

    @abstractmethod
    def get_payment_status(self, payment_hash: str) -> TxStatus:
        pass
