from abc import ABC, abstractmethod
from typing import NamedTuple, Optional


class InvoiceResponse(NamedTuple):
    ok: bool
    checking_id: Optional[str] = None  # payment_hash, rpc_id
    payment_request: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponse(NamedTuple):
    ok: bool
    checking_id: Optional[str] = None  # payment_hash, rcp_id
    fee_msat: int = 0
    error_message: Optional[str] = None


class PaymentStatus(NamedTuple):
    paid: Optional[bool] = None

    @property
    def pending(self) -> bool:
        return self.paid is not True


class Wallet(ABC):
    @abstractmethod
    def create_invoice(
        self, amount: int, memo: Optional[str] = None, description_hash: Optional[bytes] = None
    ) -> InvoiceResponse:
        pass

    @abstractmethod
    def pay_invoice(self, bolt11: str) -> PaymentResponse:
        pass

    @abstractmethod
    def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        pass

    @abstractmethod
    def get_payment_status(self, checking_id: str) -> PaymentStatus:
        pass


class Unsupported(Exception):
    pass
