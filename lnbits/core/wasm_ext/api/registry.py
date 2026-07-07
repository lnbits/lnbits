from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, cast, get_type_hints

from pydantic import BaseModel

from .models import ExtensionAPIMethod, ExtensionAPIMethodExport

_EXTENSION_API_METHOD_ATTR = "__lnbits_extension_api_method__"
_EXTENSION_RUNTIME_PERMISSION_IDS = {"ui.camera.scan_qr"}
_RequestModel = TypeVar("_RequestModel", bound=BaseModel)
_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)


def extension_api_method(
    *,
    method_id: str,
    namespace: str,
    name: str,
    host_name: str,
    sdk_name: str,
    description: str,
    host_interface: str = "host",
    required_permission: str | None = None,
    require_auth: bool = True,
) -> Callable[
    [Callable[[Any, _RequestModel], Awaitable[_ResponseModel]]],
    Callable[[Any, _RequestModel], Awaitable[_ResponseModel]],
]:
    export = ExtensionAPIMethodExport(
        method_id=method_id,
        namespace=namespace,
        name=name,
        host_interface=host_interface,
        host_name=host_name,
        sdk_name=sdk_name,
        description=description,
        required_permission=required_permission,
        require_auth=require_auth,
    )

    def decorator(
        function: Callable[[Any, _RequestModel], Awaitable[_ResponseModel]],
    ) -> Callable[[Any, _RequestModel], Awaitable[_ResponseModel]]:
        @wraps(function)
        async def wrapper(self: Any, request: _RequestModel) -> _ResponseModel:
            api = getattr(self, "api", self)
            if require_auth and not api.has_authenticated_context():
                raise PermissionError(
                    f"Extension API method '{method_id}' requires authentication."
                )
            api.require_permission(required_permission)
            return await function(self, request)

        setattr(wrapper, _EXTENSION_API_METHOD_ATTR, export)
        return wrapper

    return decorator


def list_extension_api_methods(
    api_cls: type[Any] | None = None,
) -> list[ExtensionAPIMethod]:
    api_cls = _default_api_cls(api_cls)
    methods: list[ExtensionAPIMethod] = []

    for prefix, method_cls in _extension_api_method_sources(api_cls):
        for python_name, function in inspect.getmembers(method_cls, inspect.isfunction):
            export = getattr(function, _EXTENSION_API_METHOD_ATTR, None)
            if not export:
                continue

            request_model, response_model = _get_method_models(function)
            methods.append(
                ExtensionAPIMethod(
                    method_id=export.method_id,
                    namespace=export.namespace,
                    name=export.name,
                    python_name=f"{prefix}.{python_name}" if prefix else python_name,
                    host_interface=export.host_interface,
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


def extension_api_permission_ids(api_cls: type[Any] | None = None) -> set[str]:
    permissions = {
        method.required_permission
        for method in list_extension_api_methods(api_cls)
        if method.required_permission
    }
    permissions.update(_EXTENSION_RUNTIME_PERMISSION_IDS)
    return permissions


def get_extension_api_method(
    method_id: str,
    api_cls: type[Any] | None = None,
) -> ExtensionAPIMethod:
    for method in list_extension_api_methods(api_cls):
        if method.method_id == method_id:
            return method
    raise KeyError(f"Unknown extension API method '{method_id}'.")


def extension_api_contract(api_cls: type[Any] | None = None) -> dict[str, object]:
    return {
        "version": 1,
        "methods": [
            {
                "id": method.method_id,
                "namespace": method.namespace,
                "name": method.name,
                "python_name": method.python_name,
                "host_interface": method.host_interface,
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


def _default_api_cls(api_cls: type[Any] | None) -> type[Any]:
    if api_cls is not None:
        return api_cls

    from .host import ExtensionHostAPI

    return ExtensionHostAPI


def _extension_api_method_sources(
    api_cls: type[Any],
) -> list[tuple[str, type[Any]]]:
    sources: list[tuple[str, type[Any]]] = [("", api_cls)]

    from .host import ExtensionHostAPI

    if issubclass(api_cls, ExtensionHostAPI):
        from .utils import extension_api_utils_method_classes

        sources.extend(extension_api_utils_method_classes().items())
    return sources


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
