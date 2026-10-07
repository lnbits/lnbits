from __future__ import annotations

import json
import secrets
import time
from collections.abc import Iterable, Mapping
from typing import Any

from loguru import logger

from lnbits.core.models.users import Account, UserNotifications
from lnbits.helpers import sha256s

from ..client.extensions import send_extension_api_request
from ..storage.crud import (
    OWNER_ID_FIELD,
    storage_append_public_row,
    storage_compare_and_set_row,
    storage_count_rows,
    storage_delete_row,
    storage_get_paginated_rows,
    storage_get_public_paginated_rows,
    storage_get_public_row,
    storage_get_row,
    storage_get_row_owner_id,
    storage_get_row_with_version,
    storage_insert_if_absent_row,
    storage_set_row,
)
from .background_payments import (
    WALLET_PAY_INVOICE_BACKGROUND_PERMISSION,
    _background_payment_grant,
    background_payment_extra,
    invoice_amount_msat,
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
    PayLnurlRequest,
    PaymentIntentCreateRequest,
    PaymentIntentKeyRequest,
    PaymentIntentResponse,
    RandomIdRequest,
    RandomIdResponse,
    SendUserNotificationRequest,
    SendUserNotificationResponse,
    StorageAppendPublicRequest,
    StorageAppendPublicResponse,
    StorageCompareAndSetRequest,
    StorageCompareAndSetResponse,
    StorageDeleteRequest,
    StorageDeleteResponse,
    StorageGetRequest,
    StorageGetResponse,
    StorageGetVersionedResponse,
    StorageInsertIfAbsentRequest,
    StorageInsertIfAbsentResponse,
    StoragePaginatedRequest,
    StoragePaginatedResponse,
    StoragePublicPaginatedRequest,
    StorageSetRequest,
    StorageSetResponse,
    UserWalletSummary,
    WalletBalanceRequest,
    WalletBalanceResponse,
    WebsocketPublishRequest,
    WebsocketPublishResponse,
)
from .payment_intents import (
    claim_payment_intent,
    create_or_get_payment_intent,
    get_payment_intent,
    mark_payment_intent_attempted,
    reconcile_payment_intent,
    resolve_payment_intent_invoice,
    save_payment_intent_invoice,
    set_payment_intent_status,
)
from .registry import extension_api_method
from .websockets import scoped_websocket_item_id, wasm_extension_websocket_hub

PUBLIC_APPEND_DEFAULT_MAX_ROWS_PER_SOURCE = 10_000


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
        invocation_id: str | None = None,
        runtime_limits: dict[str, int] | None = None,
    ) -> None:
        self.extension_id = extension_id
        self.permissions, self.permission_policies = self._permission_data(permissions)
        self.user_id = user_id
        self.access_token = access_token
        self.context = context
        self.owner_id = sha256s(user_id) if user_id else owner_id
        self.invocation_id = invocation_id
        self.runtime_limits = runtime_limits or {}
        from .utils import ExtensionAPIUtils

        self.utils = ExtensionAPIUtils(
            self.extension_id,
            self.permissions,
            authenticated=self.has_authenticated_context(),
        )

    @extension_api_method(
        method_id="notifications.send_user_notification",
        namespace="notifications",
        name="Send user notification",
        host_name="notifications_send_user_notification",
        sdk_name="sendUserNotification",
        description=(
            "Send a notification to the current user or the invocation's "
            "wallet owner, using their saved settings for the selected "
            "email, Nostr, or Telegram notification type. Queued does not "
            "guarantee delivery."
        ),
        required_permission="notifications.send_user_notification",
    )
    async def notifications_send_user_notification(
        self, request: SendUserNotificationRequest
    ) -> SendUserNotificationResponse:

        from lnbits.core.services.notifications import send_user_notification

        user = await self._current_user()
        if not user:
            raise PermissionError("Invocation has no notification recipient.")

        notifications = _user_notification_preferences(user, request.type)
        await send_user_notification(notifications, request.message)
        return SendUserNotificationResponse()

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
        method_id="storage.get_versioned",
        namespace="storage",
        name="Get versioned storage row",
        host_name="storage_get_versioned",
        sdk_name="getVersioned",
        description="Read one owner-scoped storage row and its concurrency version.",
        required_permission="ext.storage.read",
        require_auth=True,
    )
    async def storage_get_versioned(
        self, request: StorageGetRequest
    ) -> StorageGetVersionedResponse:
        row, version = await storage_get_row_with_version(
            self.extension_id,
            request.table,
            request.id,
            self._require_owner_id(),
        )
        return StorageGetVersionedResponse(
            data_json=json.dumps(row) if row else None,
            version=version,
        )

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
        public_fields = self._public_storage_policy(request.table)["public_fields"]
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
        method_id="storage.append_public",
        namespace="storage",
        name="Append public storage row",
        host_name="storage_append_public",
        sdk_name="appendPublic",
        description="Append one public row to an extension storage table.",
        required_permission="ext.storage.append_public",
        require_auth=False,
    )
    async def storage_append_public(
        self, request: StorageAppendPublicRequest
    ) -> StorageAppendPublicResponse:
        policy, owner_id = await self._public_storage_append_policy(
            request.table, request.source_id
        )
        data = dict(request.data)
        self._validate_public_append_data(policy, data)

        source_id_field = policy["source_id_field"]
        current_rows = await storage_count_rows(
            self.extension_id,
            request.table,
            {source_id_field: request.source_id},
            owner_id=owner_id,
        )
        if current_rows >= policy["max_rows_per_source"]:
            raise PermissionError(
                f"Public storage append limit reached for '{request.table}'."
            )

        row_id = await storage_append_public_row(
            self.extension_id,
            request.table,
            {**data, source_id_field: request.source_id},
            owner_id,
        )
        return StorageAppendPublicResponse(id=row_id)

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
        method_id="storage.compare_and_set",
        namespace="storage",
        name="Compare and set storage row",
        host_name="storage_compare_and_set",
        sdk_name="compareAndSet",
        description="Atomically update a row when its owner-scoped version matches.",
        required_permission="ext.storage.write",
        require_auth=True,
    )
    async def storage_compare_and_set(
        self, request: StorageCompareAndSetRequest
    ) -> StorageCompareAndSetResponse:
        applied = await storage_compare_and_set_row(
            self.extension_id,
            request.table,
            request.id,
            request.expected_version,
            request.new_row,
            self._require_owner_id(),
            request.make_immutable,
        )
        return StorageCompareAndSetResponse(
            applied=applied,
            version=request.expected_version + 1 if applied else None,
        )

    @extension_api_method(
        method_id="storage.insert_if_absent",
        namespace="storage",
        name="Insert storage row if absent",
        host_name="storage_insert_if_absent",
        sdk_name="insertIfAbsent",
        description="Atomically create a deterministic row without overwriting it.",
        required_permission="ext.storage.write",
        require_auth=True,
    )
    async def storage_insert_if_absent(
        self, request: StorageInsertIfAbsentRequest
    ) -> StorageInsertIfAbsentResponse:
        created, row, version = await storage_insert_if_absent_row(
            self.extension_id,
            request.table,
            request.id,
            request.new_row,
            self._require_owner_id(),
        )
        return StorageInsertIfAbsentResponse(
            created=created,
            data_json=json.dumps(row) if row else None,
            version=version,
        )

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
        method_id="storage.get_public_paginated",
        namespace="storage",
        name="Get paginated public storage rows",
        host_name="storage_get_public_paginated",
        sdk_name="getPublicPaginated",
        description="Get filtered, searched, sorted, paginated public storage rows.",
        required_permission="ext.storage.read_public",
        require_auth=False,
    )
    async def storage_get_public_paginated(
        self, request: StoragePublicPaginatedRequest
    ) -> StoragePaginatedResponse:
        policy = self._public_storage_policy(request.table)
        public_fields = policy["public_fields"]
        source_id_field = policy["source_id_field"]
        if not isinstance(source_id_field, str) or not source_id_field:
            raise PermissionError(
                "Public paginated storage reads require a source ID field policy."
            )

        filters = self._public_storage_paginated_filters(
            request, public_fields, source_id_field
        )
        page = await storage_get_public_paginated_rows(
            self.extension_id,
            request.table,
            filters,
            search=request.search,
            search_fields=request.search_fields,
            sort_by=request.sort_by,
            descending=request.descending,
            limit=request.limit,
            offset=request.offset,
        )
        return StoragePaginatedResponse(
            rows_json=json.dumps(
                [
                    {
                        field_name: value
                        for field_name, value in row.items()
                        if field_name in public_fields
                    }
                    for row in page["data"]
                ]
            ),
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
        method_id="websocket.publish",
        namespace="websocket",
        name="Publish websocket message",
        host_name="websocket_publish",
        sdk_name="publish",
        description="Publish a JSON message on an extension-local websocket channel.",
        required_permission="websocket.publish",
        require_auth=False,
    )
    async def websocket_publish(
        self, request: WebsocketPublishRequest
    ) -> WebsocketPublishResponse:
        scoped_websocket_item_id(self.extension_id, request.item_id)
        await wasm_extension_websocket_hub.publish(
            self.extension_id,
            request.item_id,
            request.data_json,
            max_messages_per_second=(self._websocket_publish_max_messages_per_second()),
        )
        return WebsocketPublishResponse()

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
        method_id="wallet.payment_intents.create_or_get",
        namespace="wallet.payment_intents",
        name="Create or get payment intent",
        host_name="wallet_payment_intent_create_or_get",
        sdk_name="createOrGet",
        description="Create or resume an idempotent, verified wallet payment.",
        required_permission="wallet.payment_intents",
        require_auth=False,
    )
    async def wallet_payment_intent_create_or_get(
        self, request: PaymentIntentCreateRequest
    ) -> PaymentIntentResponse:
        wallet, max_amount_msat = await self._payment_intent_wallet(request.wallet_id)
        intent = await create_or_get_payment_intent(
            self.extension_id,
            wallet.id,
            self._require_owner_id(),
            request,
            max_amount_msat=max_amount_msat,
        )
        current, claimed = await claim_payment_intent(self.extension_id, intent["id"])
        intent = current or intent
        if claimed:
            intent = await self._run_payment_intent(intent, wallet)
        return PaymentIntentResponse(intent_id=intent["id"], **intent)

    @extension_api_method(
        method_id="wallet.payment_intents.get_status",
        namespace="wallet.payment_intents",
        name="Get payment intent status",
        host_name="wallet_payment_intent_get_status",
        sdk_name="getStatus",
        description="Read the durable status of an idempotent wallet payment.",
        required_permission="wallet.payment_intents",
        require_auth=False,
    )
    async def wallet_payment_intent_get_status(
        self, request: PaymentIntentKeyRequest
    ) -> PaymentIntentResponse:
        await self._payment_intent_wallet(request.wallet_id)
        intent = await get_payment_intent(
            self.extension_id,
            request.wallet_id,
            request.idempotency_key,
            self._require_owner_id(),
        )
        if not intent:
            raise KeyError("Payment intent was not found.")
        return PaymentIntentResponse(intent_id=intent["id"], **intent)

    @extension_api_method(
        method_id="wallet.payment_intents.reconcile",
        namespace="wallet.payment_intents",
        name="Reconcile payment intent",
        host_name="wallet_payment_intent_reconcile",
        sdk_name="reconcile",
        description="Check the exact persisted payment and update intent status.",
        required_permission="wallet.payment_intents",
        require_auth=False,
    )
    async def wallet_payment_intent_reconcile(
        self, request: PaymentIntentKeyRequest
    ) -> PaymentIntentResponse:
        await self._payment_intent_wallet(request.wallet_id)
        intent = await get_payment_intent(
            self.extension_id,
            request.wallet_id,
            request.idempotency_key,
            self._require_owner_id(),
        )
        if not intent:
            raise KeyError("Payment intent was not found.")
        intent = await reconcile_payment_intent(self.extension_id, intent)
        return PaymentIntentResponse(intent_id=intent["id"], **intent)

    @extension_api_method(
        method_id="wallet.pay_invoice",
        namespace="wallet",
        name="Pay invoice",
        host_name="pay_invoice",
        sdk_name="payInvoice",
        description="Pay a Lightning invoice from a wallet available to the user.",
    )
    async def wallet_pay_invoice(
        self, request: PayInvoiceRequest
    ) -> PayInvoiceResponse:
        from lnbits.core.crud.wallets import get_wallet
        from lnbits.core.services.payments import pay_invoice
        from lnbits.exceptions import PaymentError

        wallet = await get_wallet(request.wallet_id)
        if wallet is None:
            raise PermissionError("Paying invoices from this wallet is not allowed.")

        try:
            if self.user_id:
                self.require_permission("wallet.pay_invoice")
                if wallet.user != self.user_id:
                    raise PermissionError(
                        "Paying invoices from this wallet is not allowed."
                    )
                payment = await pay_invoice(
                    wallet_id=request.wallet_id,
                    payment_request=request.payment_request,
                    max_sat=request.max_sat,
                    extra={"tag": self.extension_id, **request.extra},
                    description=request.description,
                    tag=self.extension_id,
                )
            else:
                self.require_permission(WALLET_PAY_INVOICE_BACKGROUND_PERMISSION)
                amount_msat = invoice_amount_msat(request.payment_request)
                extra = await background_payment_extra(
                    extension_id=self.extension_id,
                    wallet=wallet,
                    payment_request=request.payment_request,
                    amount_msat=amount_msat,
                )
                payment = await pay_invoice(
                    wallet_id=request.wallet_id,
                    payment_request=request.payment_request,
                    max_sat=request.max_sat,
                    extra={**request.extra, **extra},
                    description=request.description,
                    tag=self.extension_id,
                )
        except (PaymentError, PermissionError, ValueError) as exc:
            return PayInvoiceResponse(ok=False, error=str(exc))

        return _pay_invoice_response(payment)

    @extension_api_method(
        method_id="wallet.pay_lnurl",
        namespace="wallet",
        name="Pay LNURL",
        host_name="pay_lnurl",
        sdk_name="payLnurl",
        description="Pay a Lightning Address or LNURL-pay request from a wallet.",
    )
    async def wallet_pay_lnurl(self, request: PayLnurlRequest) -> PayInvoiceResponse:
        from lnurl import LnAddressError, LnurlResponseException

        from lnbits.core.crud.wallets import get_wallet
        from lnbits.core.models.lnurl import CreateLnurlPayment
        from lnbits.core.services.lnurl import fetch_lnurl_pay_request
        from lnbits.core.services.payments import pay_invoice
        from lnbits.exceptions import PaymentError

        from .lnurl import (
            lnurl_for_core,
            lnurl_pay_response_text,
            lnurl_payment_amount_for_core,
            lnurl_payment_unit_for_core,
        )

        wallet = await get_wallet(request.wallet_id)
        if wallet is None:
            raise PermissionError("Paying from this wallet is not allowed.")

        try:
            if self.user_id:
                self.require_permission("wallet.pay_invoice")
                if wallet.user != self.user_id:
                    raise PermissionError("Paying from this wallet is not allowed.")
            else:
                self.require_permission(WALLET_PAY_INVOICE_BACKGROUND_PERMISSION)

            unit = lnurl_payment_unit_for_core(request.currency)
            res, action = await fetch_lnurl_pay_request(
                data=CreateLnurlPayment(
                    lnurl=lnurl_for_core(request.lnurl),
                    amount=lnurl_payment_amount_for_core(request.amount),
                    unit=unit,
                    comment=request.comment,
                    internal_memo=request.description or None,
                ),
                wallet=None,
            )
            extra = {"tag": self.extension_id, **request.extra}
            if action.successAction:
                extra["success_action"] = action.successAction.json()
            if request.comment:
                extra["comment"] = request.comment
            if unit != "sat":
                extra["fiat_currency"] = unit
                extra["fiat_amount"] = str(request.amount)

            if not self.user_id:
                amount_msat = invoice_amount_msat(str(action.pr))
                extra = {
                    **extra,
                    **(
                        await background_payment_extra(
                            extension_id=self.extension_id,
                            wallet=wallet,
                            payment_request=str(action.pr),
                            amount_msat=amount_msat,
                        )
                    ),
                }

            if request.fetch_only:
                return PayInvoiceResponse(payment_request=str(action.pr))

            payment = await pay_invoice(
                wallet_id=request.wallet_id,
                payment_request=str(action.pr),
                max_sat=request.max_sat,
                extra=extra,
                description=request.description or lnurl_pay_response_text(res),
                tag=self.extension_id,
            )
        except (
            LnAddressError,
            LnurlResponseException,
            PaymentError,
            PermissionError,
            ValueError,
        ) as exc:
            logger.warning(f"Error occurred while paying invoice: {exc}")
            return PayInvoiceResponse(ok=False, error=str(exc))

        return _pay_invoice_response(payment)

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
        return await send_extension_http_request(
            self.extension_id,
            policies,
            request,
            timeout_ms=self.runtime_limits.get("wasm_runtime_http_timeout_ms"),
            max_response_bytes=self.runtime_limits.get(
                "wasm_runtime_max_http_response_bytes"
            ),
        )

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
        policies = self.permission_policies.get("extension.api.request") or []
        return await send_extension_api_request(
            self.extension_id,
            policies,
            self.user_id,
            self.access_token,
            request,
            timeout_ms=self.runtime_limits.get("wasm_runtime_http_timeout_ms"),
            max_response_bytes=self.runtime_limits.get(
                "wasm_runtime_max_http_response_bytes"
            ),
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
        logger.log(
            request.level.upper(), "extension:{} {}", self.extension_id, request.message
        )
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

    async def _current_user_id(self) -> str | None:
        from lnbits.core.crud.extensions import get_wasm_invocation
        from lnbits.core.crud.wallets import get_wallet

        if self.user_id:
            return self.user_id
        if not self.invocation_id:
            return None
        invocation = await get_wasm_invocation(self.invocation_id)
        if (
            invocation
            and invocation.extension_id == self.extension_id
            and invocation.wallet_id
        ):
            wallet = await get_wallet(invocation.wallet_id)
            return wallet.user if wallet else None
        return None

    async def _current_user(self) -> Account | None:
        from lnbits.core.crud.users import get_account

        user_id = await self._current_user_id()
        if not user_id:
            return None
        return await get_account(user_id)

    def _public_storage_policy(self, table: str) -> dict[str, Any]:
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
            source_id_field = table_policy.get("source_id_field")
            if source_id_field is not None and (
                not isinstance(source_id_field, str) or not source_id_field
            ):
                raise PermissionError(
                    f"Public storage table '{table}' has no valid source ID field."
                )
            return {
                "public_fields": set(public_fields),
                "source_id_field": source_id_field,
            }

        raise PermissionError(f"Storage table '{table}' is not publicly readable.")

    def _validate_public_storage_query_fields(
        self,
        request: StoragePaginatedRequest,
        public_fields: set[str],
        allowed_private_fields: set[str] | None = None,
    ) -> None:
        allowed_private_fields = allowed_private_fields or set()
        query_fields = set(request.filters)
        query_fields.update(request.search_fields)
        if request.sort_by:
            query_fields.add(request.sort_by)
        private_fields = sorted(query_fields - public_fields - allowed_private_fields)
        if private_fields:
            raise PermissionError(
                "Public storage query uses non-public fields: "
                + ", ".join(private_fields)
            )

    def _public_storage_paginated_filters(
        self,
        request: StoragePublicPaginatedRequest,
        public_fields: set[str],
        source_id_field: str,
    ) -> dict[str, Any]:
        self._validate_public_storage_query_fields(
            request, public_fields, {source_id_field}
        )
        filters = dict(request.filters)
        requested_source_id = filters.get(source_id_field)
        if requested_source_id is not None and requested_source_id != request.source_id:
            raise PermissionError(
                "Public storage source filter does not match source_id."
            )
        filters[source_id_field] = request.source_id
        return filters

    async def _public_storage_append_policy(
        self, table: str, source_id: str
    ) -> tuple[dict[str, Any], str]:
        policies = self.permission_policies.get("ext.storage.append_public")
        if not isinstance(policies, list) or not policies:
            raise PermissionError(
                "Public storage appends require policies for "
                "'ext.storage.append_public'."
            )

        source_not_found = False
        for raw_policy in policies:
            policy = self._normalize_public_storage_append_policy(raw_policy)
            if policy["table"] != table:
                continue
            owner_id = await storage_get_row_owner_id(
                self.extension_id,
                policy["source_table"],
                source_id,
            )
            if not owner_id:
                source_not_found = True
                continue
            return policy, owner_id

        if source_not_found:
            raise PermissionError("Public storage append source was not found.")
        raise PermissionError(f"Storage table '{table}' is not publicly appendable.")

    def _normalize_public_storage_append_policy(self, policy: Any) -> dict[str, Any]:
        if not isinstance(policy, dict):
            raise PermissionError("Public storage append policies must be objects.")

        table = policy.get("table")
        source_table = policy.get("source_table")
        source_id_field = policy.get("source_id_field")
        allowed_fields = policy.get("allowed_fields")
        max_rows_per_source = policy.get(
            "max_rows_per_source", PUBLIC_APPEND_DEFAULT_MAX_ROWS_PER_SOURCE
        )

        if not isinstance(table, str) or not table:
            raise PermissionError("Public storage append requires a table policy.")
        if not isinstance(source_table, str) or not source_table:
            raise PermissionError(
                "Public storage append requires a source table policy."
            )
        if not isinstance(source_id_field, str) or not source_id_field:
            raise PermissionError(
                "Public storage append requires a source ID field policy."
            )
        if source_id_field == "id":
            raise PermissionError("Public storage append source field cannot be 'id'.")
        if (
            not isinstance(allowed_fields, list)
            or not all(isinstance(field, str) and field for field in allowed_fields)
            or "id" in allowed_fields
            or OWNER_ID_FIELD in allowed_fields
            or source_id_field in allowed_fields
        ):
            raise PermissionError(
                "Public storage append requires valid allowed fields."
            )
        if (
            isinstance(max_rows_per_source, bool)
            or not isinstance(max_rows_per_source, int)
            or max_rows_per_source <= 0
        ):
            raise PermissionError(
                "Public storage append requires a positive row limit."
            )

        return {
            "table": table,
            "source_table": source_table,
            "source_id_field": source_id_field,
            "allowed_fields": set(allowed_fields),
            "max_rows_per_source": max_rows_per_source,
        }

    def _validate_public_append_data(
        self, policy: dict[str, Any], data: dict[str, Any]
    ) -> None:
        if not isinstance(data, dict):
            raise PermissionError("Public storage append data must be an object.")
        unknown_fields = sorted(set(data) - policy["allowed_fields"])
        if unknown_fields:
            raise PermissionError(
                "Public storage append contains disallowed fields: "
                + ", ".join(unknown_fields)
            )

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

    def _websocket_publish_max_messages_per_second(self) -> int:
        policies = self.permission_policies.get("websocket.publish")
        if not isinstance(policies, list) or len(policies) != 1:
            raise PermissionError(
                "Websocket publishing requires a max messages per second policy."
            )
        policy = policies[0]
        if not isinstance(policy, dict):
            raise PermissionError(
                "Websocket publishing requires a max messages per second policy."
            )
        max_messages_per_second = policy.get("max_messages_per_second")
        if (
            isinstance(max_messages_per_second, bool)
            or not isinstance(max_messages_per_second, int)
            or max_messages_per_second <= 0
        ):
            raise PermissionError(
                "Websocket publishing requires a valid max messages per second policy."
            )
        return max_messages_per_second

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

    async def _payment_intent_wallet(
        self, wallet_id: str
    ) -> tuple[Any, int | float | None]:
        from lnbits.core.crud.wallets import get_wallet

        wallet = await get_wallet(wallet_id)
        if not wallet:
            raise PermissionError(
                "Using this wallet for a payment intent is not allowed."
            )
        if self.user_id:
            if wallet.user != self.user_id or not wallet.can_send_payments:
                raise PermissionError(
                    "Using this wallet for a payment intent is not allowed."
                )
            return wallet, None

        self.require_permission(WALLET_PAY_INVOICE_BACKGROUND_PERMISSION)
        grant = await _background_payment_grant(self.extension_id, wallet, 0)
        return wallet, grant.max_amount * 1000

    async def _run_payment_intent(  # noqa: C901
        self, intent: dict[str, Any], wallet: Any
    ) -> dict[str, Any]:
        from lnbits.core.crud.payments import get_standalone_payment
        from lnbits.core.services.payments import fee_reserve_total, pay_invoice
        from lnbits.exceptions import PaymentError

        amount_msat = intent["amount_msat"]
        if fee_reserve_total(amount_msat) > intent["max_fee_msat"]:
            return await set_payment_intent_status(
                self.extension_id,
                intent,
                "failed",
                error="Configured fee reserve now exceeds the intent ceiling.",
            )

        try:
            (
                payment_request,
                payment_hash,
                description,
            ) = await resolve_payment_intent_invoice(intent)
            if not await save_payment_intent_invoice(
                self.extension_id, intent["id"], payment_request, payment_hash
            ):
                return (
                    await get_payment_intent(
                        self.extension_id,
                        intent["wallet_id"],
                        intent["idempotency_key"],
                        intent["owner_user_id"],
                    )
                    or intent
                )
            intent = {
                **intent,
                "payment_request": payment_request,
                "payment_hash": payment_hash,
                "checking_id": payment_hash,
            }
            extra = {"tag": self.extension_id, "extension": self.extension_id}
            if not self.user_id:
                extra.update(
                    await background_payment_extra(
                        extension_id=self.extension_id,
                        wallet=wallet,
                        payment_request=payment_request,
                        amount_msat=amount_msat,
                    )
                )
        except (PermissionError, ValueError) as exc:
            return await set_payment_intent_status(
                self.extension_id,
                intent,
                "failed",
                error=str(exc)[:512],
            )
        except Exception:
            return await set_payment_intent_status(
                self.extension_id,
                intent,
                "failed",
                error=("Destination invoice could not be prepared; retry explicitly."),
            )

        if not await mark_payment_intent_attempted(self.extension_id, intent["id"]):
            return (
                await get_payment_intent(
                    self.extension_id,
                    intent["wallet_id"],
                    intent["idempotency_key"],
                    intent["owner_user_id"],
                )
                or intent
            )
        intent = {**intent, "attempted": True}
        try:
            payment = await pay_invoice(
                wallet_id=intent["wallet_id"],
                payment_request=payment_request,
                extra=extra,
                description=(
                    description
                    or intent.get("description")
                    or f"WASM {self.extension_id} payment"
                ),
                tag=self.extension_id,
                external_id=intent["id"],
            )
        except PaymentError as exc:
            if exc.status == "failed":
                payment_record = await get_standalone_payment(
                    intent["payment_hash"], wallet_id=intent["wallet_id"]
                )
                if payment_record:
                    return await reconcile_payment_intent(self.extension_id, intent)
                return await set_payment_intent_status(
                    self.extension_id,
                    intent,
                    "failed",
                    error="Payment failed.",
                    attempted=False,
                )
            return await reconcile_payment_intent(self.extension_id, intent)
        except Exception:
            return await set_payment_intent_status(
                self.extension_id,
                intent,
                "unknown",
                error="Payment outcome is ambiguous; reconcile before retrying.",
            )

        if payment.success:
            return await set_payment_intent_status(
                self.extension_id,
                intent,
                "paid",
                fee_msat=abs(payment.fee),
            )
        if payment.failed:
            return await set_payment_intent_status(
                self.extension_id,
                intent,
                "failed",
                error="Payment failed.",
            )
        return await set_payment_intent_status(self.extension_id, intent, "pending")


def _pay_invoice_response(payment: Any) -> PayInvoiceResponse:
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


def _user_notification_preferences(
    user: Account, notification_type: str
) -> UserNotifications:
    preferences = user.extra.notifications
    return UserNotifications(
        email_address=(
            preferences.email_address if notification_type == "email" else None
        ),
        nostr_identifier=(
            preferences.nostr_identifier if notification_type == "nostr" else None
        ),
        telegram_chat_id=(
            preferences.telegram_chat_id if notification_type == "telegram" else None
        ),
    )
