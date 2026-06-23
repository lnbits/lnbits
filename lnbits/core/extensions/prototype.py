from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field

from .api import ExtensionAPI
from .models import (
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    KvGetRequest,
    KvGetResponse,
    KvListRequest,
    KvListResponse,
    KvSetRequest,
    KvSetResponse,
    WatchPaymentRequest,
    WatchPaymentResponse,
)


@dataclass
class InMemoryExtensionState:
    storage: dict[str, dict[str, str]] = field(default_factory=dict)
    payment_watchers: dict[str, dict[str, str]] = field(default_factory=dict)


class InMemoryExtensionAPI(ExtensionAPI):
    def __init__(
        self,
        extension_id: str,
        permissions: set[str],
        *,
        state: InMemoryExtensionState | None = None,
        user_id: str | None = None,
        wallet_id: str | None = None,
    ) -> None:
        super().__init__(
            extension_id,
            permissions,
            user_id=user_id,
            wallet_id=wallet_id,
        )
        self.state = state or InMemoryExtensionState()

    async def storage_get(self, request: KvGetRequest) -> KvGetResponse:
        self.require_permission("ext.storage.read_write")
        return KvGetResponse(value=self._storage.get(request.key))

    async def storage_set(self, request: KvSetRequest) -> KvSetResponse:
        self.require_permission("ext.storage.read_write")
        self._storage[request.key] = request.value
        return KvSetResponse()

    async def storage_list(self, request: KvListRequest) -> KvListResponse:
        self.require_permission("ext.storage.read_write")
        keys = sorted(key for key in self._storage if key.startswith(request.prefix))
        return KvListResponse(keys=keys)

    async def wallet_create_invoice(
        self, request: CreateInvoiceRequest
    ) -> CreateInvoiceResponse:
        self.require_permission("wallet.create_invoice")
        if self.wallet_id and request.wallet_id != self.wallet_id:
            raise PermissionError("Extension cannot create invoices for this wallet.")

        entropy = secrets.token_urlsafe(16)
        invoice_seed = (
            f"{self.extension_id}:{request.wallet_id}:{request.amount_sat}:"
            f"{request.memo}:{time.time_ns()}:{entropy}"
        )
        payment_hash = hashlib.sha256(invoice_seed.encode()).hexdigest()
        return CreateInvoiceResponse(
            payment_hash=payment_hash,
            payment_request=f"lnbits-prototype-invoice:{payment_hash}",
            checking_id=f"{self.extension_id}:{payment_hash}",
        )

    async def payments_watch(
        self, request: WatchPaymentRequest
    ) -> WatchPaymentResponse:
        self.require_permission("payments.watch")
        self.state.payment_watchers.setdefault(self.extension_id, {})[
            request.payment_hash
        ] = request.callback_export
        return WatchPaymentResponse()

    @property
    def _storage(self) -> dict[str, str]:
        return self.state.storage.setdefault(self.extension_id, {})
