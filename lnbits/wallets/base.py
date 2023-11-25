from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncGenerator, Coroutine, NamedTuple, Optional, Type

from loguru import logger

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


class PaymentStatus(NamedTuple):
    paid: Optional[bool] = None
    fee_msat: Optional[int] = None
    preimage: Optional[str] = None

    @property
    def pending(self) -> bool:
        return self.paid is not True

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


class Wallet(ABC):
    def __init__(self) -> None:
        self.pending_invoices: list[str] = []

    async def cleanup(self):
        pass

    __node_cls__: Optional[Type[Node]] = None

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


class Unsupported(Exception):
    pass
