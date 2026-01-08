from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from fastapi import Query
from lnurl import LnurlWithdrawResponse
from pydantic import BaseModel, Field, validator

from lnbits.db import FilterModel
from lnbits.fiat import get_fiat_provider
from lnbits.fiat.base import (
    FiatPaymentFailedStatus,
    FiatPaymentPendingStatus,
    FiatPaymentStatus,
    FiatPaymentSuccessStatus,
)
from lnbits.utils.exchange_rates import allowed_currencies
from lnbits.wallets import get_funding_source
from lnbits.wallets.base import (
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentStatus,
    PaymentSuccessStatus,
)


class PaymentState(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


class PaymentExtra(BaseModel):
    comment: str | None = None
    success_action: str | None = None
    lnurl_response: str | None = None


class PayInvoice(BaseModel):
    payment_request: str
    description: str | None = None
    max_sat: int | None = None
    extra: dict | None = {}


class CreatePayment(BaseModel):
    wallet_id: str
    payment_hash: str
    bolt11: str
    amount_msat: int
    memo: str
    extra: dict | None = {}
    preimage: str | None = None
    expiry: datetime | None = None
    webhook: str | None = None
    fee: int = 0
    labels: list[str] | None = None


class Payment(BaseModel):
    checking_id: str
    payment_hash: str
    wallet_id: str
    amount: int
    fee: int
    bolt11: str
    payment_request: str | None = Field(default=None, no_database=True)
    fiat_provider: str | None = None
    status: str = PaymentState.PENDING
    memo: str | None = None
    expiry: datetime | None = None
    webhook: str | None = None
    webhook_status: str | None = None
    preimage: str | None = None
    tag: str | None = None
    extension: str | None = None
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    labels: list[str] = []
    extra: dict = {}

    def __init__(self, **data):
        super().__init__(**data)
        if "fiat_payment_request" in self.extra:
            self.payment_request = self.extra["fiat_payment_request"]
        else:
            self.payment_request = self.bolt11

    @property
    def pending(self) -> bool:
        return self.status == PaymentState.PENDING.value

    @property
    def success(self) -> bool:
        return self.status == PaymentState.SUCCESS.value

    @property
    def failed(self) -> bool:
        return self.status == PaymentState.FAILED.value

    @property
    def msat(self) -> int:
        return self.amount

    @property
    def sat(self) -> int:
        return self.amount // 1000

    @property
    def is_in(self) -> bool:
        return self.amount > 0

    @property
    def is_out(self) -> bool:
        return self.amount < 0

    @property
    def is_expired(self) -> bool:
        return self.expiry < datetime.now(timezone.utc) if self.expiry else False

    @property
    def is_internal(self) -> bool:
        return self.checking_id.startswith("internal_") or self.checking_id.startswith(
            "fiat_"
        )

    async def check_status(
        self, skip_internal_payment_notifications: bool | None = False
    ) -> PaymentStatus:
        if self.is_internal:
            if self.success:
                return PaymentSuccessStatus()
            if self.failed:
                return PaymentFailedStatus()
            if self.is_in and self.fiat_provider:
                fiat_status = await self.check_fiat_status(
                    skip_internal_payment_notifications
                )
                return PaymentStatus(paid=fiat_status.paid)
            return PaymentPendingStatus()
        funding_source = get_funding_source()
        if self.is_out:
            status = await funding_source.get_payment_status(self.checking_id)
        else:
            status = await funding_source.get_invoice_status(self.checking_id)
        return status

    async def check_fiat_status(
        self, skip_internal_payment_notifications: bool | None = False
    ) -> FiatPaymentStatus:
        if not self.is_internal:
            return FiatPaymentPendingStatus()
        if self.success:
            return FiatPaymentSuccessStatus()
        if self.failed:
            return FiatPaymentFailedStatus()

        if not self.fiat_provider:
            return FiatPaymentPendingStatus()

        checking_id = self.extra.get("fiat_checking_id")
        if not checking_id:
            return FiatPaymentPendingStatus()

        fiat_provider = await get_fiat_provider(self.fiat_provider)
        if not fiat_provider:
            return FiatPaymentPendingStatus()
        fiat_status = await fiat_provider.get_invoice_status(checking_id)

        if skip_internal_payment_notifications:
            return fiat_status

        if fiat_status.success:
            # notify receivers asynchronously
            from lnbits.tasks import internal_invoice_queue

            await internal_invoice_queue.put(self.checking_id)

        return fiat_status


class PaymentFilters(FilterModel):
    __search_fields__ = [
        "memo",
        "amount",
        "wallet_id",
        "tag",
        "status",
        "time",
        "labels",
    ]

    __sort_fields__ = [
        "created_at",
        "updated_at",
        "amount",
        "fee",
        "memo",
        "time",
        "tag",
    ]

    status: str | None
    tag: str | None
    checking_id: str | None
    amount: int
    fee: int
    memo: str | None
    time: datetime
    preimage: str | None
    payment_hash: str | None
    wallet_id: str | None
    labels: str | None


class PaymentDataPoint(BaseModel):
    date: datetime
    count: int
    max_amount: int
    min_amount: int
    average_amount: int
    total_amount: int
    max_fee: int
    min_fee: int
    average_fee: int
    total_fee: int


PaymentCountField = Literal["status", "tag", "extension", "wallet_id"]


class PaymentCountStat(BaseModel):
    field: str = ""
    total: float = 0


class PaymentWalletStats(BaseModel):
    wallet_id: str = ""
    wallet_name: str = ""
    user_id: str = ""
    payments_count: int
    balance: float = 0


class PaymentDailyStats(BaseModel):
    date: datetime
    balance: float = 0
    balance_in: float | None = 0
    balance_out: float | None = 0
    payments_count: int = 0
    count_in: int | None = 0
    count_out: int | None = 0
    fee: float = 0


class PaymentHistoryPoint(BaseModel):
    date: datetime
    income: int
    spending: int
    balance: int


class DecodePayment(BaseModel):
    data: str
    filter_fields: list[str] | None = []


class CreateInvoice(BaseModel):
    unit: str = "sat"
    internal: bool = False
    out: bool = True
    amount: float = Query(None, ge=0)
    memo: str | None = Query(None, max_length=640)
    description_hash: str | None = None
    unhashed_description: str | None = None
    payment_hash: str | None = Query(
        None,
        description="The payment hash of the hold invoice.",
        min_length=64,
        max_length=64,
    )
    expiry: int | None = None
    extra: dict | None = None
    webhook: str | None = None
    bolt11: str | None = None
    lnurl_withdraw: LnurlWithdrawResponse | None = None
    fiat_provider: str | None = None
    labels: list[str] = []

    @validator("payment_hash")
    def check_hex(cls, v):
        if v:
            _ = bytes.fromhex(v)
        return v

    @validator("unit")
    @classmethod
    def unit_is_from_allowed_currencies(cls, v):
        if v != "sat" and v not in allowed_currencies():
            raise ValueError("The provided unit is not supported")
        return v


class PaymentsStatusCount(BaseModel):
    incoming: int = 0
    outgoing: int = 0
    failed: int = 0
    pending: int = 0


class SettleInvoice(BaseModel):
    preimage: str = Field(
        ...,
        description="The preimage of the payment hash to settle the invoice.",
        min_length=64,
        max_length=64,
    )

    @validator("preimage")
    def check_hex(cls, v):
        _ = bytes.fromhex(v)
        return v


class CancelInvoice(BaseModel):
    payment_hash: str = Field(
        ...,
        description="The payment hash of the invoice to cancel.",
        min_length=64,
        max_length=64,
    )

    @validator("payment_hash")
    def check_hex(cls, v):
        _ = bytes.fromhex(v)
        return v


class UpdatePaymentLabels(BaseModel):
    labels: list[str] = []
