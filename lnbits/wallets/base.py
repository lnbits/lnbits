from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Coroutine
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple

from loguru import logger

from lnbits.exceptions import InvoiceError
from lnbits.settings import settings

if TYPE_CHECKING:
    from lnbits.nodes.base import Node


class Feature(Enum):
    nodemanager = "nodemanager"
    holdinvoice = "holdinvoice"
    # bolt12 = "bolt12"


class StatusResponse(NamedTuple):
    error_message: str | None
    balance_msat: int


class InvoiceResponse(NamedTuple):
    ok: bool
    checking_id: str | None = None  # payment_hash, rpc_id
    payment_request: str | None = None
    error_message: str | None = None
    preimage: str | None = None
    fee_msat: int | None = None

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


class Wallet(ABC):

    __node_cls__: type[Node] | None = None
    features: list[Feature] | None = None

    def has_feature(self, feature: Feature) -> bool:
        return self.features is not None and feature in self.features

    def __init__(self) -> None:
        self.pending_invoices: list[str] = []

    @abstractmethod
    async def cleanup(self):
        pass

    @abstractmethod
    def status(self) -> Coroutine[None, None, StatusResponse]:
        pass

    @abstractmethod
    def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
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

    async def create_hold_invoice(
        self,
        amount: int,
        payment_hash: str,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        raise InvoiceError(
            message="Hold invoices are not supported by this wallet.", status="failed"
        )

    async def settle_hold_invoice(self, preimage: str) -> InvoiceResponse:
        raise InvoiceError(
            message="Hold invoices are not supported by this wallet.", status="failed"
        )

    async def cancel_hold_invoice(self, payment_hash: str) -> InvoiceResponse:
        raise InvoiceError(
            message="Hold invoices are not supported by this wallet.", status="failed"
        )

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            for invoice in self.pending_invoices:
                try:
                    status = await self.get_invoice_status(invoice)
                    if status.paid:
                        yield invoice
                        self.pending_invoices.remove(invoice)
                    elif status.failed:
                        self.pending_invoices.remove(invoice)
                except Exception as exc:
                    logger.error(f"could not get status of invoice {invoice}: '{exc}' ")
            await asyncio.sleep(5)
