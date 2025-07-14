from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Coroutine
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple

from bolt11 import Bolt11, Tags
from bolt11 import decode as bolt11_decode
from bolt11 import encode as bolt11_encode
from bolt11.exceptions import Bolt11Bech32InvalidException

from loguru import logger

from lnbits.utils.crypto import fake_privkey, random_secret_and_hash
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
    payment_secret: str | None = None
    payer_note: str | None = None
    amount_msat: int | None = None
    offer_id: str | None = None
    offer_issuer_id: str | None = None
    invoice_node_id: str | None = None
    offer_absolute_expiry: int | None = None
    invoice_created_at: int | None = None
    invoice_relative_expiry: int | None = None
    bolt11: str | None = None
    bolt11_is_fake: bool | None = None


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
        return self.paid is False

    @property
    def failed(self) -> bool:
        return self.paid is None


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

    async def decode_offer(self, bolt12_offer: str) -> Optional[OfferData]:
        return None

    async def decode_invoice(self, invoice_string: str) -> Optional[InvoiceData]:
        try:
            invoice = bolt11_decode(invoice_string)
            return InvoiceData(payment_hash = invoice.payment_hash,
                               description = invoice.description,
                               description_hash = invoice.description_hash,
                               payment_secret = invoice.payment_secret,
                               amount_msat = invoice.amount_msat,
                               offer_issuer_id = invoice.payee,
                               invoice_node_id = invoice.payee,
                               invoice_created_at = invoice.date,
                               invoice_relative_expiry = invoice.expiry,
                               bolt11 = invoice_string,
                               bolt11_is_fake = False)

        except Bolt11Bech32InvalidException as exc:
            return None
        except Exception as exc:
            logger.warning(exc)
            return None

    async def get_invoice_extended_status(
            self,
            checking_id: str,
            offer_id: Optional[str] = None
            ) -> Optional[InvoiceExtendedStatus]:
        return None

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

    def generate_fake_bolt11(
            self,
            created_at: int,
            amount_msat: int | None = None,
            description: str | None = None,
            expire_time: int | None = None
            ) -> str:
        payment_secret, payment_hash = random_secret_and_hash()
        dict_tags = {
                    "payment_hash": payment_hash,
                    "payment_secret": payment_secret,
                }

        if description:
            dict_tags["description"] = description

        if expire_time:
            dict_tags["expire_time"] = expire_time
        bolt11_invoice = Bolt11(
            currency="bc",
            amount_msat=amount_msat,
            date=created_at,
            tags=Tags.from_dict(dict_tags),
        )
        privkey = fake_privkey(settings.fake_wallet_secret)
        return bolt11_encode(bolt11_invoice, privkey)

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
