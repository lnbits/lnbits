from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncGenerator, Coroutine, NamedTuple

from loguru import logger

if TYPE_CHECKING:
    from lnbits.nodes.base import Node


class StatusResponse(NamedTuple):
    error_message: str | None
    balance_msat: int


class OfferResponse(NamedTuple):
    ok: bool
    offer_id: str | None = None 
    active: bool | None = None
    single_use: bool | None = None
    invoice_offer: str | None = None
    used: bool | None = None
    created: bool | None = None
    label: str | None = None
    error_message: str | None = None

    @property
    def success(self) -> bool:
        return self.ok is True

    @property
    def failed(self) -> bool:
        return self.ok is not True


class OfferStatus(NamedTuple):
    active: bool | None = None
    used: bool | None = None

    @property
    def active(self) -> bool:
        return self.active is True

    @property
    def used(self) -> bool:
        return self.used is True

    @property
    def error(self) -> bool:
        return self.active is None


class OfferErrorStatus(OfferStatus):
    active = None
    used = None


class FetchInvoiceResponse(NamedTuple):
    ok: bool
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


class OfferData(NamedTuple):
    offer_id: str
    currency: str | None = None
    currency_amount: float | None = None
    amount_msat: int | None = None
    description: str | None = None
    issuer: str | None = None
    absolute_expiry: int | None = None
    offer_issuer_id: str | None = None


class InvoiceData(NamedTuple):
    payment_hash: str | None = None
    description: str | None = None
    description_hash: str | None = None
    payer_note: str | None = None
    amount_msat: int | None = None
    offer_id: str | None = None
    offer_issuer_id: str | None = None
    invoice_node_id: str | None = None
    offer_absolute_expiry: int | None = None
    invoice_created_at: int | None = None
    invoice_relative_expiry: int | None = None


class InvoiceResponse(NamedTuple):
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


class InvoiceExtendedStatus(NamedTuple):
    paid: bool | None = None
    string: str | None = None
    offer_id: str | None = None
    paid_at: int | None = None
    payment_preimage: str | None = None

    @property
    def success(self) -> bool:
        return self.paid is True

    @property
    def pending(self) -> bool:
        return self.paid is None

    @property
    def failed(self) -> bool:
        return self.paid is False


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

    async def decode_offer(self, bolt12_offer: str) -> Optional[OfferData]:
        return None

    async def decode_invoice(self, invoice_string: str) -> Optional[InvoiceData]:
        return None

    async def get_invoice_extended_status(self, checking_id: str) -> Optional[InvoiceExtendedStatus]:
        return None

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
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
