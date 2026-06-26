from __future__ import annotations

import inspect
import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from functools import wraps
from typing import NoReturn, TypeVar, cast, get_type_hints

from pydantic import BaseModel

from .models import (
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
    StorageListRequest,
    StorageListResponse,
    StoragePaginatedRequest,
    StoragePaginatedResponse,
    StorageSetRequest,
    StorageSetResponse,
    WatchPaymentRequest,
    WatchPaymentResponse,
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
    )

    def decorator(
        function: Callable[[ExtensionAPI, _RequestModel], Awaitable[_ResponseModel]],
    ) -> Callable[[ExtensionAPI, _RequestModel], Awaitable[_ResponseModel]]:
        @wraps(function)
        async def wrapper(self: ExtensionAPI, request: _RequestModel) -> _ResponseModel:
            self.require_permission(required_permission)
            return await function(self, request)

        setattr(wrapper, _EXTENSION_API_METHOD_ATTR, export)
        return wrapper

    return decorator


class ExtensionAPI:
    def __init__(
        self,
        extension_id: str,
        permissions: Iterable[str],
        *,
        user_id: str | None = None,
        wallet_id: str | None = None,
    ) -> None:
        self.extension_id = extension_id
        self.permissions = set(permissions)
        self.user_id = user_id
        self.wallet_id = wallet_id

    def require_permission(self, permission: str | None) -> None:
        if permission and permission not in self.permissions:
            raise PermissionError(
                f"Extension '{self.extension_id}' is missing permission '{permission}'."
            )

    @extension_api_method(
        method_id="storage.get",
        namespace="storage",
        name="Get storage row",
        host_name="storage_get",
        sdk_name="get",
        description="Read one row from an extension storage table.",
        required_permission="ext.storage.read_write",
    )
    async def storage_get(self, request: StorageGetRequest) -> StorageGetResponse:
        self._raise_unwired_runtime("storage_get")

    @extension_api_method(
        method_id="storage.set",
        namespace="storage",
        name="Set storage row",
        host_name="storage_set",
        sdk_name="set",
        description="Create or update one row in an extension storage table.",
        required_permission="ext.storage.read_write",
    )
    async def storage_set(self, request: StorageSetRequest) -> StorageSetResponse:
        self._raise_unwired_runtime("storage_set")

    @extension_api_method(
        method_id="storage.list",
        namespace="storage",
        name="List storage rows",
        host_name="storage_list",
        sdk_name="list",
        description="List rows from an extension storage table.",
        required_permission="ext.storage.read_write",
    )
    async def storage_list(self, request: StorageListRequest) -> StorageListResponse:
        self._raise_unwired_runtime("storage_list")

    @extension_api_method(
        method_id="storage.get_paginated",
        namespace="storage",
        name="Get paginated storage rows",
        host_name="storage_get_paginated",
        sdk_name="getPaginated",
        description="Get filtered, searched, sorted, paginated storage rows.",
        required_permission="ext.storage.read_write",
    )
    async def storage_get_paginated(
        self, request: StoragePaginatedRequest
    ) -> StoragePaginatedResponse:
        self._raise_unwired_runtime("storage_get_paginated")

    @extension_api_method(
        method_id="storage.delete",
        namespace="storage",
        name="Delete storage row",
        host_name="storage_delete",
        sdk_name="delete",
        description="Delete one row from an extension storage table.",
        required_permission="ext.storage.read_write",
    )
    async def storage_delete(
        self, request: StorageDeleteRequest
    ) -> StorageDeleteResponse:
        self._raise_unwired_runtime("storage_delete")

    @extension_api_method(
        method_id="wallet.create_invoice",
        namespace="wallet",
        name="Create invoice",
        host_name="create_invoice",
        sdk_name="createInvoice",
        description="Create an incoming Lightning invoice for an allowed wallet.",
        required_permission="wallet.create_invoice",
    )
    async def wallet_create_invoice(
        self, request: CreateInvoiceRequest
    ) -> CreateInvoiceResponse:
        self._raise_unwired_runtime("wallet_create_invoice")

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
        self._raise_unwired_runtime("wallet_list_user_wallets")

    @extension_api_method(
        method_id="payments.watch",
        namespace="payments",
        name="Watch payment",
        host_name="watch_payment",
        sdk_name="watch",
        description="Subscribe the extension to a payment state callback.",
        required_permission="payments.watch",
    )
    async def payments_watch(
        self, request: WatchPaymentRequest
    ) -> WatchPaymentResponse:
        self._raise_unwired_runtime("payments_watch")

    @extension_api_method(
        method_id="system.random_id",
        namespace="system",
        name="Random ID",
        host_name="random_id",
        sdk_name="id",
        description="Create a random extension-local identifier.",
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
    )
    async def system_log(self, request: LogRequest) -> LogResponse:
        log = getattr(logger, request.level)
        log("extension:%s %s", self.extension_id, request.message)
        return LogResponse()

    def _raise_unwired_runtime(self, method_name: str) -> NoReturn:
        raise NotImplementedError(
            f"ExtensionAPI.{method_name} must be wired to LNbits services before use."
        )


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
            )
        )

    return sorted(methods, key=lambda method: method.method_id)


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
