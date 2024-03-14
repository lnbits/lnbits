from __future__ import annotations

from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Coroutine,
    List,
    NamedTuple,
    Optional,
    Type,
)

if TYPE_CHECKING:
    from lnbits.nodes.base import Node


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
    fee_msat: Optional[int] = None
    preimage: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponseSuccess(PaymentResponse):
    ok = True


class PaymentResponseFailed(PaymentResponse):
    ok = False


class PaymentResponsePending(PaymentResponse):
    ok = None


class PaymentStatus(NamedTuple):
    paid: Optional[bool] = None
    fee_msat: Optional[int] = None
    preimage: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.paid is True

    @property
    def pending(self) -> bool:
        return self.paid is None

    @property
    def failed(self) -> bool:
        return self.paid is False

    def __str__(self) -> str:
        if self.paid is True:
            return "settled"
        elif self.paid is False:
            return "failed"
        elif self.paid is None:
            return "still pending"
        else:
            return "unknown (should never happen)"


class PaymentSuccessStatus(PaymentStatus):
    paid = True


class PaymentFailedStatus(PaymentStatus):
    paid = False


class PaymentPendingStatus(PaymentStatus):
    paid = None


class PaymentStatusMap(NamedTuple):
    """
    LNbits has 3 possible statuses for a payment.
    This class maps these 3 statuses to a particular funding source statuses.
    """

    success: List[str | int | bool | None]
    failed: List[str | int | bool | None]
    pending: List[str | int | bool | None]


class Wallet(ABC):
    async def cleanup(self):
        pass

    __node_cls__: Optional[Type[Node]] = None

    @property
    @abstractmethod
    def payment_status_map(self) -> PaymentStatusMap:
        """
        Each funding source returns its own custom payment status values.
        This method maps the custom statuses to a common format.
        """
        pass

    @abstractmethod
    def status(self) -> Coroutine[None, None, StatusResponse]:
        pass

    @abstractmethod
    def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> Coroutine[None, None, InvoiceResponse]:
        pass

    @abstractmethod
    def pay_invoice(
        self, bolt11: str, fee_limit_msat: int
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

    @abstractmethod
    def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        pass

    def payment_status(
        self,
        status: Optional[int] = None,
        fee_msat: Optional[int] = None,
        preimage: Optional[str] = None,
    ) -> PaymentStatus:
        status_map = self.payment_status_map
        if status in status_map.success:
            return PaymentSuccessStatus(fee_msat=fee_msat, preimage=preimage)
        if status in status_map.failed:
            return PaymentFailedStatus(fee_msat=fee_msat, preimage=preimage)
        if status in status_map.pending:
            return PaymentPendingStatus(fee_msat=fee_msat, preimage=preimage)
        return PaymentPendingStatus()

    def normalize_endpoint(self, endpoint: str, add_proto=True) -> str:
        endpoint = endpoint[:-1] if endpoint.endswith("/") else endpoint
        if add_proto:
            endpoint = (
                f"https://{endpoint}" if not endpoint.startswith("http") else endpoint
            )
        return endpoint


class Unsupported(Exception):
    pass
