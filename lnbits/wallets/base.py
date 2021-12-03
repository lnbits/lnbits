from abc import ABC, abstractmethod
from typing import NamedTuple, Optional, AsyncGenerator, Coroutine


class StatusResponse(NamedTuple):
    error_message: Optional[str]
    balance_msat: int


class InvoiceResponse(NamedTuple):
    ok: bool
    checking_id: Optional[str] = None  # payment_hash, rpc_id
    payment_request: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponse(NamedTuple):
    # when ok is None it means we don't know if this succeeded
    ok: Optional[bool] = None
    checking_id: Optional[str] = None  # payment_hash, rcp_id
    fee_msat: int = 0
    preimage: Optional[str] = None
    error_message: Optional[str] = None


class PaymentStatus(NamedTuple):
    paid: Optional[bool] = None

    @property
    def pending(self) -> bool:
        return self.paid is not True

    @property
    def failed(self) -> bool:
        return self.paid == False

    def __str__(self) -> str:
        if self.paid == True:
            return "settled"
        elif self.paid == False:
            return "failed"
        elif self.paid == None:
            return "still pending"
        else:
            return "unknown (should never happen)"


class Wallet(ABC):
    @abstractmethod
    def status(self) -> Coroutine[None, None, StatusResponse]:
        pass

    @abstractmethod
    def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
    ) -> Coroutine[None, None, InvoiceResponse]:
        pass

    # WARNING: correct handling of fee_limit_msat is required to avoid security vulnerabilities!
    # The backend MUST NOT spend satoshis above invoice amount + fee_limit_msat.
    @abstractmethod
    def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> Coroutine[None, None, PaymentResponse]:
        pass

    @abstractmethod
    def get_invoice_status(
        self, checking_id: str
    ) -> Coroutine[None, None, PaymentStatus]:
        pass

    @abstractmethod
    def get_payment_status(
        self, checking_id: str
    ) -> Coroutine[None, None, PaymentStatus]:
        pass

    @abstractmethod
    def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        pass


class Unsupported(Exception):
    pass
