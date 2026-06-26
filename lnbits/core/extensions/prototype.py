from __future__ import annotations

import json
from dataclasses import dataclass, field

from .api import ExtensionAPI
from .models import (
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    EmptyRequest,
    ListUserWalletsResponse,
    StorageDeleteRequest,
    StorageDeleteResponse,
    StorageGetRequest,
    StorageGetResponse,
    StorageListRequest,
    StorageListResponse,
    StoragePaginatedRequest,
    StoragePaginatedResponse,
    StorageSetRequest,
    StorageSetResponse,
    UserWalletSummary,
    WatchPaymentRequest,
    WatchPaymentResponse,
)
from .storage import (
    storage_delete_row,
    storage_get_paginated_rows,
    storage_get_row,
    storage_list_rows,
    storage_set_row,
)


@dataclass
class InMemoryExtensionState:
    payment_watchers: dict[str, dict[str, str]] = field(default_factory=dict)
    user_wallets: dict[str, list[UserWalletSummary] | None] = field(
        default_factory=dict
    )


class InMemoryExtensionAPI(ExtensionAPI):
    def __init__(
        self,
        extension_id: str,
        permissions: set[str],
        *,
        state: InMemoryExtensionState | None = None,
        user_id: str | None = None,
    ) -> None:
        super().__init__(extension_id, permissions, user_id=user_id)
        self.state = state or InMemoryExtensionState()

    async def storage_get(self, request: StorageGetRequest) -> StorageGetResponse:
        self.require_permission("ext.storage.read_write")
        row = await storage_get_row(self.extension_id, request.table, request.id)
        return StorageGetResponse(data_json=json.dumps(row) if row else None)

    async def storage_set(self, request: StorageSetRequest) -> StorageSetResponse:
        self.require_permission("ext.storage.read_write")
        await storage_set_row(self.extension_id, request.table, request.data)
        return StorageSetResponse()

    async def storage_list(self, request: StorageListRequest) -> StorageListResponse:
        self.require_permission("ext.storage.read_write")
        rows = await storage_list_rows(
            self.extension_id,
            request.table,
            request.filters,
            limit=request.limit,
            offset=request.offset,
        )
        return StorageListResponse(rows_json=json.dumps(rows))

    async def storage_get_paginated(
        self, request: StoragePaginatedRequest
    ) -> StoragePaginatedResponse:
        self.require_permission("ext.storage.read_write")
        page = await storage_get_paginated_rows(
            self.extension_id,
            request.table,
            request.filters,
            search=request.search,
            search_fields=request.search_fields,
            sort_by=request.sort_by,
            descending=request.descending,
            limit=request.limit,
            offset=request.offset,
        )
        return StoragePaginatedResponse(
            rows_json=json.dumps(page["data"]),
            total=page["total"],
        )

    async def storage_delete(
        self, request: StorageDeleteRequest
    ) -> StorageDeleteResponse:
        self.require_permission("ext.storage.read_write")
        await storage_delete_row(self.extension_id, request.table, request.id)
        return StorageDeleteResponse()

    async def wallet_create_invoice(
        self, request: CreateInvoiceRequest
    ) -> CreateInvoiceResponse:
        self.require_permission("wallet.create_invoice")

        from lnbits.core.crud.wallets import get_wallet
        from lnbits.core.models.payments import CreateInvoice
        from lnbits.core.services.payments import create_payment_request

        if self.user_id:
            wallet = await get_wallet(request.wallet_id)
            if wallet is None or wallet.user != self.user_id:
                raise PermissionError(
                    "Creating an invoice for this wallet requires an "
                    "authenticated user context."
                )
        else:
            pass
            # todo: security stuff here

        payment = await create_payment_request(
            request.wallet_id,
            CreateInvoice(
                amount=request.amount_sat,
                unit=request.currency or "sat",
                memo=request.memo,
                extra=request.extra,
            ),
        )
        return CreateInvoiceResponse(
            payment_hash=payment.payment_hash,
            payment_request=payment.payment_request or payment.bolt11,
            checking_id=payment.checking_id,
        )

    async def wallet_list_user_wallets(
        self, _request: EmptyRequest
    ) -> ListUserWalletsResponse:
        self.require_permission("wallet.list")
        if not self.user_id:
            raise PermissionError(
                "Listing user wallets requires an authenticated user context."
            )

        from lnbits.core.crud.wallets import get_wallets

        user_wallets = await get_wallets(self.user_id)
        if user_wallets is None:
            raise PermissionError(
                "Listing user wallets requires an authenticated user context."
            )
        return ListUserWalletsResponse(
            wallets=[
                UserWalletSummary(id=w.id, name=w.name, currency=w.currency)
                for w in user_wallets
            ]
        )

    async def payments_watch(
        self, request: WatchPaymentRequest
    ) -> WatchPaymentResponse:
        self.require_permission("payments.watch")
        self.state.payment_watchers.setdefault(self.extension_id, {})[
            request.payment_hash
        ] = request.callback_export
        return WatchPaymentResponse()
