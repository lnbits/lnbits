from __future__ import annotations

import inspect
import json
import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar, cast, get_type_hints

from pydantic import BaseModel

from lnbits.helpers import sha256s

from .models import (
    CreateInvoicePublicRequest,
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    EmptyRequest,
    ListUserWalletsResponse,
    LogRequest,
    LogResponse,
    NowResponse,
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
)
from .storage import (
    storage_delete_row,
    storage_get_paginated_rows,
    storage_get_public_row,
    storage_get_row,
    storage_set_row,
)

logger = logging.getLogger("lnbits.extensions")

_EXTENSION_API_METHOD_ATTR = "__lnbits_extension_api_method__"
_RequestModel = TypeVar("_RequestModel", bound=BaseModel)
_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)


@dataclass(frozen=True)
class ExtensionAPIMethodExport:
    method_id: str
    namespace: str
    name: str
    host_name: str
    sdk_name: str
    description: str
    required_permission: str | None = None
    require_auth: bool = True


@dataclass(frozen=True)
class ExtensionAPIMethod:
    method_id: str
    namespace: str
    name: str
    python_name: str
    host_name: str
    sdk_name: str
    description: str
    request_model: type[BaseModel]
    response_model: type[BaseModel]
    required_permission: str | None = None
    require_auth: bool = True

    @property
    def sdk_qualified_name(self) -> str:
        return f"{self.namespace}.{self.sdk_name}"


def extension_api_method(
    *,
    method_id: str,
    namespace: str,
    name: str,
    host_name: str,
    sdk_name: str,
    description: str,
    required_permission: str | None = None,
    require_auth: bool = True,
) -> Callable[
    [Callable[[ExtensionAPI, _RequestModel], Awaitable[_ResponseModel]]],
    Callable[[ExtensionAPI, _RequestModel], Awaitable[_ResponseModel]],
]:
    export = ExtensionAPIMethodExport(
        method_id=method_id,
        namespace=namespace,
        name=name,
        host_name=host_name,
        sdk_name=sdk_name,
        description=description,
        required_permission=required_permission,
        require_auth=require_auth,
    )

    def decorator(
        function: Callable[[ExtensionAPI, _RequestModel], Awaitable[_ResponseModel]],
    ) -> Callable[[ExtensionAPI, _RequestModel], Awaitable[_ResponseModel]]:
        @wraps(function)
        async def wrapper(self: ExtensionAPI, request: _RequestModel) -> _ResponseModel:
            if require_auth and not self.has_authenticated_context():
                raise PermissionError(
                    f"Extension API method '{method_id}' requires authentication."
                )
            self.require_permission(required_permission)
            return await function(self, request)

        setattr(wrapper, _EXTENSION_API_METHOD_ATTR, export)
        return wrapper

    return decorator


class ExtensionAPI:
    def __init__(
        self,
        extension_id: str,
        permissions: Iterable[Any],
        *,
        user_id: str | None = None,
        context: str = "user",
        owner_id: str | None = None,
    ) -> None:
        self.extension_id = extension_id
        self.permissions, self.permission_policies = self._permission_data(permissions)
        self.user_id = user_id
        self.context = context
        self.owner_id = sha256s(user_id) if user_id else owner_id
        self._uuid = secrets.token_urlsafe(12).replace("-", "_")

    def __repr__(self) -> str:
        return (
            "ExtensionAPI("
            f"extension_id={self.extension_id!r}, "
            f"context={self.context!r}, "
            f"_uuid={self._uuid!r}"
            ")"
        )

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

        table, wallet_field = self._public_invoice_wallet_source()
        row = await storage_get_public_row(self.extension_id, table, request.source_id)
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
    ) -> tuple[set[str], dict[str, dict[str, Any]]]:
        permission_ids: set[str] = set()
        policies: dict[str, dict[str, Any]] = {}

        for permission in permissions:
            if isinstance(permission, str):
                permission_ids.add(permission)
                continue

            permission_id: str | None = None
            policy: Any = None
            if isinstance(permission, Mapping):
                permission_id = permission.get("id")  # type: ignore[assignment]
                policy = permission.get("policy")
            else:
                permission_id = getattr(permission, "id", None)
                policy = getattr(permission, "policy", None)

            if not permission_id:
                continue
            permission_ids.add(permission_id)
            if isinstance(policy, dict):
                policies[permission_id] = policy

        return permission_ids, policies

    def _public_storage_fields(self, table: str) -> set[str]:
        policy = self.permission_policies.get("ext.storage.read_public") or {}
        tables = policy.get("tables")
        if not isinstance(tables, list):
            raise PermissionError(
                "Public storage reads require a tables policy for "
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

    def _public_invoice_wallet_source(self) -> tuple[str, str]:
        policy = self.permission_policies.get("wallet.create_invoice_public") or {}
        table = policy.get("table")
        wallet_field = policy.get("wallet_field")
        if not isinstance(table, str) or not table:
            raise PermissionError(
                "Public invoice creation requires a storage table policy."
            )
        if not isinstance(wallet_field, str) or not wallet_field:
            raise PermissionError(
                "Public invoice creation requires a wallet field policy."
            )
        return table, wallet_field


def list_extension_api_methods(
    api_cls: type[ExtensionAPI] = ExtensionAPI,
) -> list[ExtensionAPIMethod]:
    methods: list[ExtensionAPIMethod] = []

    for python_name, function in inspect.getmembers(api_cls, inspect.isfunction):
        export = getattr(function, _EXTENSION_API_METHOD_ATTR, None)
        if not export:
            continue

        request_model, response_model = _get_method_models(function)
        methods.append(
            ExtensionAPIMethod(
                method_id=export.method_id,
                namespace=export.namespace,
                name=export.name,
                python_name=python_name,
                host_name=export.host_name,
                sdk_name=export.sdk_name,
                description=export.description,
                request_model=request_model,
                response_model=response_model,
                required_permission=export.required_permission,
                require_auth=export.require_auth,
            )
        )

    return sorted(methods, key=lambda method: method.method_id)


def extension_api_permission_ids(
    api_cls: type[ExtensionAPI] = ExtensionAPI,
) -> set[str]:
    return {
        method.required_permission
        for method in list_extension_api_methods(api_cls)
        if method.required_permission
    }


def get_extension_api_method(
    method_id: str,
    api_cls: type[ExtensionAPI] = ExtensionAPI,
) -> ExtensionAPIMethod:
    for method in list_extension_api_methods(api_cls):
        if method.method_id == method_id:
            return method
    raise KeyError(f"Unknown extension API method '{method_id}'.")


def extension_api_contract(
    api_cls: type[ExtensionAPI] = ExtensionAPI,
) -> dict[str, object]:
    return {
        "version": 1,
        "methods": [
            {
                "id": method.method_id,
                "namespace": method.namespace,
                "name": method.name,
                "python_name": method.python_name,
                "host_name": method.host_name,
                "sdk_name": method.sdk_name,
                "sdk_qualified_name": method.sdk_qualified_name,
                "description": method.description,
                "required_permission": method.required_permission,
                "require_auth": method.require_auth,
                "request_schema": method.request_model.schema(
                    ref_template="#/definitions/{model}"
                ),
                "response_schema": method.response_model.schema(
                    ref_template="#/definitions/{model}"
                ),
            }
            for method in list_extension_api_methods(api_cls)
        ],
    }


def _get_method_models(
    function: Callable[..., object],
) -> tuple[type[BaseModel], type[BaseModel]]:
    signature = inspect.signature(function)
    request_parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.name != "self"
    ]
    if len(request_parameters) != 1:
        raise TypeError(
            f"Extension API method '{function.__name__}' must accept one request model."
        )

    hints = get_type_hints(function)
    request_model = hints.get(request_parameters[0].name)
    response_model = hints.get("return")

    if not _is_pydantic_model(request_model):
        raise TypeError(
            f"Extension API method '{function.__name__}' request must be a BaseModel."
        )
    if not _is_pydantic_model(response_model):
        raise TypeError(
            f"Extension API method '{function.__name__}' response must be a BaseModel."
        )

    return cast(type[BaseModel], request_model), cast(type[BaseModel], response_model)


def _is_pydantic_model(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)
