from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Coroutine
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    pass


class FiatStatusResponse(NamedTuple):
    error_message: str | None = None
    balance: float = 0


class FiatInvoiceResponse(NamedTuple):
    ok: bool
    checking_id: str | None = None  # payment_hash, rpc_id
    payment_request: str | None = None
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


class FiatPaymentResponse(NamedTuple):
    # when ok is None it means we don't know if this succeeded
    ok: bool | None = None
    checking_id: str | None = None  # payment_hash, rcp_id
    fee: float | None = None
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


class FiatPaymentStatus(NamedTuple):
    paid: bool | None = None
    fee: float | None = None  # todo: what fee is this?

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


class FiatPaymentSuccessStatus(FiatPaymentStatus):
    paid = True


class FiatPaymentFailedStatus(FiatPaymentStatus):
    paid = False


class FiatPaymentPendingStatus(FiatPaymentStatus):
    paid = None


class FiatProvider(ABC):
    @abstractmethod
    async def cleanup(self):
        pass

    @abstractmethod
    def status(
        self, only_check_settings: bool | None = False
    ) -> Coroutine[None, None, FiatStatusResponse]:
        pass

    @abstractmethod
    def create_invoice(
        self,
        amount: float,
        payment_hash: str,
        currency: str,
        memo: str | None = None,
        **kwargs,
    ) -> Coroutine[None, None, FiatInvoiceResponse]:
        pass

    @abstractmethod
    def pay_invoice(
        self,
        payment_request: str,
    ) -> Coroutine[None, None, FiatPaymentResponse]:
        pass

    @abstractmethod
    def get_invoice_status(
        self, checking_id: str
    ) -> Coroutine[None, None, FiatPaymentStatus]:
        pass

    @abstractmethod
    def get_payment_status(
        self, checking_id: str
    ) -> Coroutine[None, None, FiatPaymentStatus]:
        pass

    async def paid_invoices_stream(
        self,
    ) -> AsyncGenerator[str, None]:
        yield ""
