from __future__ import annotations

import inspect
import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from functools import wraps
from typing import Literal, TypeVar, get_type_hints

from pydantic import BaseModel, Field

logger = logging.getLogger("lnbits.extensions")

_EXTENSION_API_METHOD_ATTR = "__lnbits_extension_api_method__"
_RequestModel = TypeVar("_RequestModel", bound=BaseModel)
_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)


class EmptyRequest(BaseModel):
    pass


class KvGetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=512)


class KvGetResponse(BaseModel):
    value: str | None = None


class KvSetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=512)
    value: str = Field(..., max_length=65536)


class KvSetResponse(BaseModel):
    ok: bool = True


class KvListRequest(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=512)


class KvListResponse(BaseModel):
    keys: list[str] = Field(default_factory=list)


class CreateInvoiceRequest(BaseModel):
    wallet_id: str = Field(..., min_length=1, max_length=128)
    amount_sat: int = Field(..., gt=0)
    memo: str = Field(..., max_length=512)
    tag: str = Field(..., min_length=1, max_length=64)
    extra: dict[str, str] = Field(default_factory=dict)


class CreateInvoiceResponse(BaseModel):
    payment_hash: str
    payment_request: str
    checking_id: str


class WatchPaymentRequest(BaseModel):
    payment_hash: str = Field(..., min_length=1, max_length=128)
    callback_export: str = Field(..., min_length=1, max_length=128)


class WatchPaymentResponse(BaseModel):
    ok: bool = True


class RandomIdRequest(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=32)


class RandomIdResponse(BaseModel):
    id: str


class NowResponse(BaseModel):
    timestamp: int


class LogRequest(BaseModel):
    level: Literal["debug", "info", "warning", "error"] = "info"
    message: str = Field(..., min_length=1, max_length=2048)


class LogResponse(BaseModel):
    ok: bool = True


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
    [Callable[["ExtensionAPI", _RequestModel], Awaitable[_ResponseModel]]],
    Callable[["ExtensionAPI", _RequestModel], Awaitable[_ResponseModel]],
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
        function: Callable[["ExtensionAPI", _RequestModel], Awaitable[_ResponseModel]],
    ) -> Callable[["ExtensionAPI", _RequestModel], Awaitable[_ResponseModel]]:
        @wraps(function)
        async def wrapper(
            self: "ExtensionAPI", request: _RequestModel
        ) -> _ResponseModel:
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
        name="Get storage value",
        host_name="kv_get",
        sdk_name="get",
        description="Read one value from the extension storage namespace.",
        required_permission="ext.storage.read_write",
    )
    async def storage_get(self, request: KvGetRequest) -> KvGetResponse:
        self._raise_unwired_runtime("storage_get")

    @extension_api_method(
        method_id="storage.set",
        namespace="storage",
        name="Set storage value",
        host_name="kv_set",
        sdk_name="set",
        description="Write one value to the extension storage namespace.",
        required_permission="ext.storage.read_write",
    )
    async def storage_set(self, request: KvSetRequest) -> KvSetResponse:
        self._raise_unwired_runtime("storage_set")

    @extension_api_method(
        method_id="storage.list",
        namespace="storage",
        name="List storage keys",
        host_name="kv_list",
        sdk_name="list",
        description="List keys under a prefix in the extension storage namespace.",
        required_permission="ext.storage.read_write",
    )
    async def storage_list(self, request: KvListRequest) -> KvListResponse:
        self._raise_unwired_runtime("storage_list")

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
        method_id="payments.watch",
        namespace="payments",
        name="Watch payment",
        host_name="watch_payment",
        sdk_name="watch",
        description="Subscribe the extension to a payment state callback.",
        required_permission="payments.watch",
    )
    async def payments_watch(self, request: WatchPaymentRequest) -> WatchPaymentResponse:
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

    def _raise_unwired_runtime(self, method_name: str) -> None:
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

    return request_model, response_model


def _is_pydantic_model(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)
