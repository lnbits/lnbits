from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from fastapi import FastAPI

from lnbits.core.crud.extensions import get_installed_extension
from lnbits.core.db import core_app_extra

from .api import ExtensionAPI, list_extension_api_methods
from .loader import WasmExtension
from .runtime import ExtensionAPIHost


async def invoke_wasm_extension_export(
    app: FastAPI,
    ext_id: str,
    export_name: str,
    payload: Mapping[str, Any] | None = None,
    *,
    user: Any | None = None,
    context: str = "user",
    owner_id: str | None = None,
) -> dict[str, Any]:
    extension = _get_registered_extension(ext_id)
    permissions = await _extension_permissions(extension)
    api = ExtensionAPI(
        extension.id,
        permissions,
        user_id=_user_id(user),
        context=context,
        owner_id=owner_id,
    )
    print("### api", api)

    return await asyncio.to_thread(
        _invoke_wasm_extension_export_sync,
        extension,
        export_name,
        payload or {},
        api,
    )


def warm_wasm_extension(extension: WasmExtension) -> None:
    _wasm_component(extension)


def _invoke_wasm_extension_export_sync(
    extension: WasmExtension,
    export_name: str,
    payload: Mapping[str, Any],
    api: ExtensionAPI,
) -> dict[str, Any]:
    try:
        from wasmtime import Store, WasiConfig, component
    except ImportError as exc:
        raise RuntimeError(
            "WASM extension runtime is not installed. Install the 'wasmtime' "
            "Python package to run WASM extensions."
        ) from exc

    engine = _wasm_engine()
    store = Store(engine)
    store.set_wasi(WasiConfig())

    linker = component.Linker(engine)
    linker.add_wasip2()
    _add_extension_host_imports(linker, ExtensionAPIHost(api))

    wasm_component = _wasm_component(extension)
    instance = linker.instantiate(store, wasm_component)
    function = instance.get_func(store, export_name)
    if not function:
        raise KeyError(
            f"WASM extension '{extension.id}' has no export '{export_name}'."
        )

    result = function(store, json.dumps(payload))
    function.post_return(store)
    return _parse_wasm_export_result(extension, result)


@lru_cache(maxsize=1)
def _wasm_engine() -> Any:
    try:
        from wasmtime import Config, Engine
    except ImportError as exc:
        raise RuntimeError(
            "WASM extension runtime is not installed. Install the 'wasmtime' "
            "Python package to run WASM extensions."
        ) from exc

    config = Config()
    config.wasm_component_model = True
    return Engine(config)


def _wasm_component(extension: WasmExtension) -> Any:
    stat = extension.module_path.stat()
    return _cached_wasm_component(
        str(extension.module_path),
        stat.st_mtime_ns,
        stat.st_size,
    )


@lru_cache(maxsize=32)
def _cached_wasm_component(
    module_path: str,
    mtime_ns: int,
    size: int,
) -> Any:
    from wasmtime import component

    return component.Component.from_file(_wasm_engine(), module_path)


def _add_extension_host_imports(linker: Any, api_host: ExtensionAPIHost) -> None:
    with linker.root() as root:
        with root.add_instance("lnbits:extension/host") as host:
            for method in list_extension_api_methods():
                host.add_func(
                    method.host_name.replace("_", "-"),
                    _make_host_import(api_host, method.host_name),
                )


def _make_host_import(api_host: ExtensionAPIHost, host_name: str) -> Any:
    def host_import(_store: Any, request: Any = None) -> Any:
        payload = _component_payload_to_dict(request)
        response = asyncio.run(api_host.invoke(host_name, payload))
        return _dict_to_component_record(response)

    return host_import


def _component_payload_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("WASM host function payload must be a record.")


def _dict_to_component_record(value: Mapping[str, Any]) -> Any:
    from wasmtime import component

    record = component.Record()
    for key, item in value.items():
        setattr(record, _camel_to_kebab(key), _to_component_value(item))
    return record


def _to_component_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _dict_to_component_record(value)
    if isinstance(value, list):
        return [_to_component_value(item) for item in value]
    return value


def _parse_wasm_export_result(extension: WasmExtension, value: Any) -> dict[str, Any]:
    if isinstance(value, bytes):
        value = value.decode()
    if not isinstance(value, str):
        return {"ok": True, "data": value}

    max_response_bytes = (
        (extension.config.get("wasm") or {})
        .get("resource_limits", {})
        .get("max_response_bytes")
    )
    if isinstance(max_response_bytes, int):
        response_size = len(value.encode())
        if response_size > max_response_bytes:
            raise ValueError(
                f"WASM extension response is too large: {response_size} bytes."
            )

    parsed = json.loads(value)
    if isinstance(parsed, dict):
        return parsed
    return {"ok": True, "data": parsed}


def _get_registered_extension(ext_id: str) -> WasmExtension:
    extension = core_app_extra.wasm_extension_registry.get(ext_id)
    if extension:
        return extension
    raise RuntimeError(f"WASM extension '{ext_id}' is not registered.")


async def _extension_permissions(extension: WasmExtension) -> list[Any]:
    installed_extension = await get_installed_extension(extension.id)
    if not installed_extension:
        return []
    return installed_extension.permissions


def _user_id(user: Any | None) -> str | None:
    return getattr(user, "id", None) if user else None


def _camel_to_kebab(value: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value).replace("_", "-").lower()
