from __future__ import annotations

from dataclasses import dataclass, field



from .api import ExtensionAPI
from .models import (
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    EmptyRequest,
    KvGetRequest,
    KvGetResponse,
    KvListRequest,
    KvListResponse,
    KvSetRequest,
    KvSetResponse,
    ListUserWalletsResponse,
    UserWalletSummary,
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
        user_wallets: list[UserWalletSummary] | None = None,
    ) -> None:
        super().__init__(
            extension_id,
            permissions,
            user_id=user_id,
            wallet_id=wallet_id,
        )
        self.state = state or InMemoryExtensionState()
        self.user_wallets = list(user_wallets) if user_wallets is not None else None

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

        from lnbits.core.models.payments import CreateInvoice
        from lnbits.core.services.payments import create_payment_request
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
        if self.user_wallets is None:
            raise PermissionError(
                "Listing user wallets requires an authenticated user context."
            )
        return ListUserWalletsResponse(wallets=self.user_wallets)

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
