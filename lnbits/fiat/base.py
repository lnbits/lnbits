from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Coroutine
from typing import TYPE_CHECKING, Any, NamedTuple

from pydantic import BaseModel, Field

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


class FiatSubscriptionPaymentOptions(BaseModel):

    memo: str | None = Field(
        default=None,
        description="Payments created by the recurring subscription"
        " will have this memo.",
    )
    wallet_id: str | None = Field(
        default=None,
        description="Payments created by the recurring subscription"
        " will be made to this wallet.",
    )
    subscription_request_id: str | None = Field(
        default=None,
        description="Unique ID that can be used to identify the subscription request."
        "If not provided, one will be generated.",
    )
    tag: str | None = Field(
        default=None,
        description="Payments created by the recurring subscription"
        " will have this tag. Admin only.",
    )
    extra: dict[str, Any] | None = Field(
        default=None,
        description="Payments created by the recurring subscription"
        " will merge this extra data to the payment extra. Admin only.",
    )

    success_url: str | None = Field(
        default="https://my.lnbits.com",
        description="The URL to redirect the user to after the"
        " subscription is successfully created.",
    )


class CreateFiatSubscription(BaseModel):
    subscription_id: str
    quantity: int
    payment_options: FiatSubscriptionPaymentOptions


class FiatSubscriptionResponse(BaseModel):
    ok: bool = True
    subscription_request_id: str | None = None
    checkout_session_url: str | None = None
    error_message: str | None = None


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
        extra: dict[str, Any] | None = None,
        **kwargs,
    ) -> Coroutine[None, None, FiatInvoiceResponse]:
        pass

    @abstractmethod
    def create_subscription(
        self,
        subscription_id: str,
        quantity: int,
        payment_options: FiatSubscriptionPaymentOptions,
        **kwargs,
    ) -> Coroutine[None, None, FiatSubscriptionResponse]:
        pass

    @abstractmethod
    def cancel_subscription(
        self,
        subscription_id: str,
        correlation_id: str,
        **kwargs,
    ) -> Coroutine[None, None, FiatSubscriptionResponse]:
        """
        Cancel a subscription.
        Args:
            subscription_id: The ID of the subscription to cancel.
            correlation_id: An identifier used to verify that the subscription belongs
                            to the user that made the request. Usually the wallet ID.
        """
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
