from __future__ import annotations

import json
import logging
import secrets
import time
from collections.abc import Iterable, Mapping
from typing import Any

from lnbits.helpers import sha256s

from ..storage.crud import (
    storage_delete_row,
    storage_get_paginated_rows,
    storage_get_public_row,
    storage_get_row,
    storage_set_row,
)
from .models import (
    CreateInvoicePublicRequest,
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    EmptyRequest,
    ExtensionApiRequest,
    HttpRequest,
    HttpResponse,
    ListUserWalletsResponse,
    LogRequest,
    LogResponse,
    NowResponse,
    PayInvoiceRequest,
    PayInvoiceResponse,
    RandomIdRequest,
    RandomIdResponse,
    StorageDeleteRequest,
    StorageDeleteResponse,
    StorageGetRequest,
    StorageGetResponse,
    StoragePaginatedRequest,
    StoragePaginatedResponse,
    StorageSetRequest,
    StorageSetResponse,
    UserWalletSummary,
    WalletBalanceRequest,
    WalletBalanceResponse,
)
from .registry import extension_api_method

logger = logging.getLogger("lnbits.extensions")


class ExtensionHostAPI:
    def __init__(
        self,
        extension_id: str,
        permissions: Iterable[Any],
        *,
        user_id: str | None = None,
        access_token: str | None = None,
        context: str = "user",
        owner_id: str | None = None,
    ) -> None:
        self.extension_id = extension_id
        self.permissions, self.permission_policies = self._permission_data(permissions)
        self.user_id = user_id
        self.access_token = access_token
        self.context = context
        self.owner_id = sha256s(user_id) if user_id else owner_id
        from .utils import ExtensionAPIUtils

        self.utils = ExtensionAPIUtils(self)

    @extension_api_method(
        method_id="storage.get",
        namespace="storage",
        name="Get storage row",
        host_name="storage_get",
        sdk_name="get",
        description="Read one row from an extension storage table.",
        required_permission="ext.storage.read",
        require_auth=True,
    )
    async def storage_get(self, request: StorageGetRequest) -> StorageGetResponse:
        row = await storage_get_row(
            self.extension_id,
            request.table,
            request.id,
            self._require_owner_id(),
        )
        return StorageGetResponse(data_json=json.dumps(row) if row else None)

    @extension_api_method(
        method_id="storage.get_public",
        namespace="storage",
        name="Get public storage row",
        host_name="storage_get_public",
        sdk_name="getPublic",
        description="Read one public row from an extension storage table.",
        required_permission="ext.storage.read_public",
        require_auth=False,
    )
    async def storage_get_public(
        self, request: StorageGetRequest
    ) -> StorageGetResponse:
        public_fields = self._public_storage_fields(request.table)
        row = await storage_get_public_row(self.extension_id, request.table, request.id)
        if not row:
            return StorageGetResponse()
        public_row = {
            field_name: value
            for field_name, value in row.items()
            if field_name in public_fields
        }
        # todo: check public fields filtering
        return StorageGetResponse(data_json=json.dumps(public_row))

    @extension_api_method(
        method_id="storage.set",
        namespace="storage",
        name="Set storage row",
        host_name="storage_set",
        sdk_name="set",
        description="Create or update one row in an extension storage table.",
        required_permission="ext.storage.write",
        require_auth=True,
    )
    async def storage_set(self, request: StorageSetRequest) -> StorageSetResponse:
        await storage_set_row(
            self.extension_id,
            request.table,
            request.data,
            self._require_owner_id(),
        )
        return StorageSetResponse()

    @extension_api_method(
        method_id="storage.get_paginated",
        namespace="storage",
        name="Get paginated storage rows",
        host_name="storage_get_paginated",
        sdk_name="getPaginated",
        description="Get filtered, searched, sorted, paginated storage rows.",
        required_permission="ext.storage.read",
        require_auth=True,
    )
    async def storage_get_paginated(
        self, request: StoragePaginatedRequest
    ) -> StoragePaginatedResponse:
        page = await storage_get_paginated_rows(
            self.extension_id,
            request.table,
            request.filters,
            owner_id=self._require_owner_id(),
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

    @extension_api_method(
        method_id="storage.delete",
        namespace="storage",
        name="Delete storage row",
        host_name="storage_delete",
        sdk_name="delete",
        description="Delete one row from an extension storage table.",
        required_permission="ext.storage.write",
        require_auth=True,
    )
    async def storage_delete(
        self, request: StorageDeleteRequest
    ) -> StorageDeleteResponse:
        await storage_delete_row(
            self.extension_id,
            request.table,
            request.id,
            self._require_owner_id(),
        )
        return StorageDeleteResponse()

    @extension_api_method(
        method_id="wallet.create_invoice",
        namespace="wallet",
        name="Create invoice",
        host_name="create_invoice",
        sdk_name="createInvoice",
        description="Create an incoming Lightning invoice for an allowed wallet.",
        required_permission="wallet.create_invoice",
        require_auth=True,
    )
    async def wallet_create_invoice(
        self, request: CreateInvoiceRequest
    ) -> CreateInvoiceResponse:
        from lnbits.core.crud.wallets import get_wallet
        from lnbits.core.models.payments import CreateInvoice
        from lnbits.core.services.payments import create_payment_request

        if not self.user_id:
            raise PermissionError(
                "Creating an invoice for this wallet requires an "
                "authenticated user context."
            )
        wallet = await get_wallet(request.wallet_id)
        if wallet is None or wallet.user != self.user_id:
            raise PermissionError("Not your wallet.")

        payment = await create_payment_request(
            request.wallet_id,
            CreateInvoice(
                amount=request.amount,
                unit=request.currency,
                memo=request.memo,
                extra=request.extra,
                extension=self.extension_id,
            ),
        )
        return CreateInvoiceResponse(
            payment_hash=payment.payment_hash,
            payment_request=payment.payment_request or payment.bolt11,
            checking_id=payment.checking_id,
        )

    @extension_api_method(
        method_id="wallet.create_invoice_public",
        namespace="wallet",
        name="Create public invoice",
        host_name="create_invoice_public",
        sdk_name="createInvoicePublic",
        description="Create a public incoming Lightning invoice.",
        required_permission="wallet.create_invoice_public",
        require_auth=False,
    )
    async def wallet_create_invoice_public(
        self, request: CreateInvoicePublicRequest
    ) -> CreateInvoiceResponse:
        from lnbits.core.models.payments import CreateInvoice
        from lnbits.core.services.payments import create_payment_request

        row: dict[str, Any] | None = None
        wallet_field = ""
        for policy in self._public_invoice_wallet_sources():
            row = await storage_get_public_row(
                self.extension_id,
                policy["table"],
                request.source_id,
            )
            if row:
                wallet_field = policy["wallet_field"]
                break

        if not row:
            raise PermissionError("Public invoice source was not found.")

        wallet_id = row.get(wallet_field)
        if not isinstance(wallet_id, str) or not wallet_id:
            raise PermissionError("Public invoice source has no valid wallet.")

        payment = await create_payment_request(
            wallet_id,
            CreateInvoice(
                amount=request.amount,
                unit=request.currency,
                memo=request.memo,
                extra={
                    "tag": self.extension_id,
                    "source_id": request.source_id,
                    f"extra_{self.extension_id}": request.extra,
                },
                extension=self.extension_id,
            ),
        )
        return CreateInvoiceResponse(
            payment_hash=payment.payment_hash,
            payment_request=payment.payment_request or payment.bolt11,
            checking_id=payment.checking_id,
        )

    @extension_api_method(
        method_id="wallet.list_user_wallets",
        namespace="wallet",
        name="List user wallets",
        host_name="list_user_wallets",
        sdk_name="listUserWallets",
        description="List wallets available to the authenticated extension user.",
        required_permission="wallet.list",
    )
    async def wallet_list_user_wallets(
        self, request: EmptyRequest
    ) -> ListUserWalletsResponse:
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

    @extension_api_method(
        method_id="wallet.balance",
        namespace="wallet",
        name="Read wallet balance",
        host_name="wallet_balance",
        sdk_name="balance",
        description="Read the balance of a wallet available to the user.",
        required_permission="wallet.balance.read",
    )
    async def wallet_balance(
        self, request: WalletBalanceRequest
    ) -> WalletBalanceResponse:
        from lnbits.core.crud.wallets import get_wallet

        if not self.user_id:
            raise PermissionError(
                "Reading a wallet balance requires an authenticated user context."
            )

        wallet = await get_wallet(request.wallet_id)
        if wallet is None or wallet.user != self.user_id:
            raise PermissionError("Reading this wallet balance is not allowed.")

        withdrawable_msat = max(wallet.withdrawable_balance, 0)
        fee_reserve_msat = max(wallet.balance_msat - withdrawable_msat, 0)
        return WalletBalanceResponse(
            wallet_id=wallet.id,
            name=wallet.name,
            currency=wallet.currency,
            balance_msat=wallet.balance_msat,
            balance_sat=wallet.balance,
            withdrawable_msat=withdrawable_msat,
            withdrawable_sat=withdrawable_msat // 1000,
            fee_reserve_msat=fee_reserve_msat,
            fee_reserve_sat=fee_reserve_msat // 1000,
            can_send_payments=wallet.can_send_payments,
        )

    @extension_api_method(
        method_id="wallet.pay_invoice",
        namespace="wallet",
        name="Pay invoice",
        host_name="pay_invoice",
        sdk_name="payInvoice",
        description="Pay a Lightning invoice from a wallet available to the user.",
        required_permission="wallet.pay_invoice",
    )
    async def wallet_pay_invoice(
        self, request: PayInvoiceRequest
    ) -> PayInvoiceResponse:
        from lnbits.core.crud.wallets import get_wallet
        from lnbits.core.services.payments import pay_invoice
        from lnbits.exceptions import PaymentError

        if not self.user_id:
            raise PermissionError(
                "Paying an invoice requires an authenticated user context."
            )

        wallet = await get_wallet(request.wallet_id)
        if wallet is None or wallet.user != self.user_id:
            raise PermissionError("Paying invoices from this wallet is not allowed.")

        try:
            payment = await pay_invoice(
                wallet_id=request.wallet_id,
                payment_request=request.payment_request,
                max_sat=request.max_sat,
                extra={"tag": self.extension_id, **request.extra},
                description=request.description,
                tag=self.extension_id,
            )
        except (PaymentError, ValueError) as exc:
            return PayInvoiceResponse(ok=False, error=str(exc))

        return PayInvoiceResponse(
            ok=True,
            checking_id=payment.checking_id,
            payment_hash=payment.payment_hash,
            status=payment.status,
            amount_msat=abs(payment.amount),
            fee_msat=abs(payment.fee),
            pending=payment.pending,
            success=payment.success,
        )

    @extension_api_method(
        method_id="http.request",
        namespace="http",
        name="HTTP request",
        host_name="http_request",
        sdk_name="request",
        description="Make an outbound HTTP request to an allowed host.",
        required_permission="http.request",
        require_auth=True,
    )
    async def http_request(self, request: HttpRequest) -> HttpResponse:
        from ..client.http import send_extension_http_request

        policies = self.permission_policies.get("http.request") or []
        return await send_extension_http_request(self.extension_id, policies, request)

    @extension_api_method(
        method_id="extension.api.request",
        namespace="extension",
        name="Extension API request",
        host_name="extension_api_request",
        sdk_name="request",
        description="Call an allowed installed extension API.",
        required_permission="extension.api.request",
        require_auth=True,
    )
    async def extension_api_request(self, request: ExtensionApiRequest) -> HttpResponse:
        from ..client.extensions import send_extension_api_request

        policies = self.permission_policies.get("extension.api.request") or []
        return await send_extension_api_request(
            self.extension_id,
            policies,
            self.user_id,
            self.access_token,
            request,
        )

    @extension_api_method(
        method_id="system.random_id",
        namespace="system",
        name="Random ID",
        host_name="random_id",
        sdk_name="id",
        description="Create a random extension-local identifier.",
        require_auth=False,
    )
    async def system_random_id(self, request: RandomIdRequest) -> RandomIdResponse:
        return RandomIdResponse(
            id=f"{request.prefix}_{secrets.token_urlsafe(12).replace('-', '_')}"
        )

    @extension_api_method(
        method_id="system.now",
        namespace="system",
        name="Current timestamp",
        host_name="now",
        sdk_name="now",
        description="Return the current Unix timestamp.",
        require_auth=False,
    )
    async def system_now(self, request: EmptyRequest) -> NowResponse:
        return NowResponse(timestamp=int(time.time()))

    @extension_api_method(
        method_id="system.log",
        namespace="system",
        name="Log message",
        host_name="log",
        sdk_name="log",
        description="Write a bounded message to the extension log.",
        require_auth=False,
    )
    async def system_log(self, request: LogRequest) -> LogResponse:
        log = getattr(logger, request.level)
        log("extension:%s %s", self.extension_id, request.message)
        return LogResponse()

    @staticmethod
    def _permission_data(
        permissions: Iterable[Any],
    ) -> tuple[set[str], dict[str, list[Any]]]:
        permission_ids: set[str] = set()
        policies: dict[str, list[Any]] = {}

        for permission in permissions:
            if isinstance(permission, str):
                permission_ids.add(permission)
                continue

            permission_id: str | None = None
            permission_policies: Any = None
            if isinstance(permission, Mapping):
                permission_id = permission.get("id")  # type: ignore[assignment]
                permission_policies = permission.get("policies")
            else:
                permission_id = getattr(permission, "id", None)
                permission_policies = getattr(permission, "policies", None)

            if not permission_id:
                continue
            permission_ids.add(permission_id)
            if isinstance(permission_policies, list):
                policies[permission_id] = permission_policies

        return permission_ids, policies

    def _public_storage_fields(self, table: str) -> set[str]:
        tables = self.permission_policies.get("ext.storage.read_public")
        if not isinstance(tables, list) or not tables:
            raise PermissionError(
                "Public storage reads require policies for "
                "'ext.storage.read_public'."
            )

        for table_policy in tables:
            if not isinstance(table_policy, dict):
                continue
            if table_policy.get("table_name") != table:
                continue
            public_fields = table_policy.get("public_fields")
            if not isinstance(public_fields, list) or not all(
                isinstance(field, str) and field for field in public_fields
            ):
                raise PermissionError(
                    f"Public storage table '{table}' has no valid public fields."
                )
            return set(public_fields)

        raise PermissionError(f"Storage table '{table}' is not publicly readable.")

    def _public_invoice_wallet_sources(self) -> list[dict[str, str]]:
        policies = self.permission_policies.get("wallet.create_invoice_public")
        if not isinstance(policies, list) or not policies:
            raise PermissionError("Public invoice creation requires a policies list.")

        sources: list[dict[str, str]] = []
        for source_policy in policies:
            if not isinstance(source_policy, dict):
                raise PermissionError(
                    "Public invoice creation policies must be objects."
                )
            table = source_policy.get("table")
            wallet_field = source_policy.get("wallet_field")
            if not isinstance(table, str) or not table:
                raise PermissionError(
                    "Public invoice creation requires a storage table policy."
                )
            if not isinstance(wallet_field, str) or not wallet_field:
                raise PermissionError(
                    "Public invoice creation requires a wallet field policy."
                )
            sources.append({"table": table, "wallet_field": wallet_field})

        if not sources:
            raise PermissionError(
                "Public invoice creation requires at least one valid policy."
            )
        return sources

    def require_permission(self, permission: str | None) -> None:
        if permission and permission not in self.permissions:
            raise PermissionError(
                f"Extension '{self.extension_id}' is missing permission '{permission}'."
            )

    def has_authenticated_context(self) -> bool:
        return bool(self.user_id) or self.context == "event"

    def _require_owner_id(self) -> str:
        if not self.owner_id:
            raise PermissionError("Extension API method requires an owner context.")
        return self.owner_id

    def __repr__(self) -> str:
        return (
            "ExtensionHostAPI("
            f"extension_id={self.extension_id!r}, "
            f"context={self.context!r}, "
            f"owner_id={self.owner_id!r}"
            ")"
        )
