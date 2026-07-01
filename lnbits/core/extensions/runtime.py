from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import BaseModel

from .api import ExtensionAPI, ExtensionAPIMethod, list_extension_api_methods

HostImport = Callable[..., Awaitable[dict[str, Any]]]


class ExtensionAPIHost:
    def __init__(
        self,
        api: ExtensionAPI,
        *,
        api_cls: type[ExtensionAPI] = ExtensionAPI,
    ) -> None:
        self.api = api
        self.methods = list_extension_api_methods(api_cls)
        self._methods_by_host_name = self._index_methods(self.methods)

    async def invoke(
        self,
        host_name: str,
        payload: Mapping[str, Any] | BaseModel | None = None,
    ) -> dict[str, Any]:
        method = self._require_method(host_name)
        request = self._request_model(method, payload)
        handler = getattr(self.api, method.python_name)
        response = handler(request)
        if inspect.isawaitable(response):
            response = await response
        return self._response_payload(method, response)

    def imports(self) -> dict[str, HostImport]:
        return {
            _snake_to_camel(method.host_name): self._make_import(method)
            for method in self.methods
        }

    def import_object(self) -> dict[str, dict[str, HostImport]]:
        return {"lnbits:extension/host": self.imports()}

    def _make_import(self, method: ExtensionAPIMethod) -> HostImport:
        async def host_import(
            payload: Mapping[str, Any] | BaseModel | None = None,
        ) -> dict[str, Any]:
            return await self.invoke(method.host_name, payload)

        return host_import

    def _require_method(self, host_name: str) -> ExtensionAPIMethod:
        method = self._methods_by_host_name.get(host_name)
        if not method:
            raise KeyError(f"Unknown extension host function '{host_name}'.")
        return method

    @staticmethod
    def _index_methods(
        methods: list[ExtensionAPIMethod],
    ) -> dict[str, ExtensionAPIMethod]:
        index: dict[str, ExtensionAPIMethod] = {}
        for method in methods:
            for host_name in {
                method.host_name,
                _snake_to_camel(method.host_name),
                method.host_name.replace("_", "-"),
            }:
                index[host_name] = method
        return index

    @staticmethod
    def _request_model(
        method: ExtensionAPIMethod,
        payload: Mapping[str, Any] | BaseModel | None,
    ) -> BaseModel:
        if isinstance(payload, method.request_model):
            return payload
        if isinstance(payload, BaseModel):
            payload = payload.dict()
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"Host function '{method.host_name}' expects an object payload."
            )
        data = {_to_snake(key): value for key, value in payload.items()}
        if isinstance(data.get("extra"), list):
            data["extra"] = dict(data["extra"])
        if isinstance(data.get("headers"), list):
            data["headers"] = dict(data["headers"])
        return method.request_model.parse_obj(data)

    @staticmethod
    def _response_payload(
        method: ExtensionAPIMethod,
        response: Any,
    ) -> dict[str, Any]:
        if not isinstance(response, method.response_model):
            response = method.response_model.parse_obj(response)
        payload = response.dict()
        if method.method_id in {"http.request", "extension.api.request"} and isinstance(
            payload.get("headers"), Mapping
        ):
            payload["headers"] = list(payload["headers"].items())
        return {_snake_to_camel(key): value for key, value in payload.items()}


def _snake_to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _to_snake(value: str) -> str:
    value = value.replace("-", "_")
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()
