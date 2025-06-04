from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncGenerator, Coroutine, NamedTuple

if TYPE_CHECKING:
    pass


class FiatStatusResponse(NamedTuple):
    error_message: str | None = None
    balance: float = 0
    currency: str = "usd"


class InvoiceResponse(NamedTuple):
    ok: bool
    checking_id: str | None = None  # payment_hash, rpc_id
    payment_request: str | None = None
    error_message: str | None = None
    preimage: str | None = None

    @property
    def success(self) -> bool:
        return self.ok is True

    @property
    def pending(self) -> bool:
        return self.ok is None

    @property
    def failed(self) -> bool:
        return self.ok is False


class PaymentResponse(NamedTuple):
    # when ok is None it means we don't know if this succeeded
    ok: bool | None = None
    checking_id: str | None = None  # payment_hash, rcp_id
    fee_msat: int | None = None
    preimage: str | None = None
    error_message: str | None = None

    @property
    def success(self) -> bool:
        return self.ok is True

    @property
    def pending(self) -> bool:
        return self.ok is None

    @property
    def failed(self) -> bool:
        return self.ok is False


class PaymentStatus(NamedTuple):
    paid: bool | None = None
    fee_msat: int | None = None
    preimage: str | None = None

    @property
    def success(self) -> bool:
        return self.paid is True

    @property
    def pending(self) -> bool:
        return self.paid is not True

    @property
    def failed(self) -> bool:
        return self.paid is False

    def __str__(self) -> str:
        if self.success:
            return "success"
        if self.failed:
            return "failed"
        return "pending"


class PaymentSuccessStatus(PaymentStatus):
    paid = True


class PaymentFailedStatus(PaymentStatus):
    paid = False


class PaymentPendingStatus(PaymentStatus):
    paid = None


class FiatWallet(ABC):
    @abstractmethod
    async def cleanup(self):
        pass

    @abstractmethod
    def status(self) -> Coroutine[None, None, FiatStatusResponse]:
        pass

    @abstractmethod
    def create_invoice(
        self,
        amount: int,
        payment_hash: str,
        currency: str,
        memo: str | None = None,
        **kwargs,
    ) -> Coroutine[None, None, InvoiceResponse]:
        pass

    @abstractmethod
    def pay_invoice(
        self,
        payment_request: str,
    ) -> Coroutine[None, None, PaymentResponse]:
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

    async def paid_invoices_stream(
        self,
    ) -> AsyncGenerator[str, None]:
        yield ""

    def normalize_endpoint(self, endpoint: str, add_proto=True) -> str:
        endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        if add_proto:
            if endpoint.startswith("ws://") or endpoint.startswith("wss://"):
                return endpoint
            endpoint = (
                f"https://{endpoint}" if not endpoint.startswith("http") else endpoint
            )
        return endpoint


class UnsupportedError(Exception):
    pass
