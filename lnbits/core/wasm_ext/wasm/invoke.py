from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from lnbits.core.crud.extensions import get_installed_extension
from lnbits.core.db import core_app_extra

from ..api.host import ExtensionHostAPI
from ..api.runtime import ExtensionAPIHost
from .component import _wasm_component, _wasm_engine
from .host import add_extension_host_imports
from .loader import WasmExtension


async def invoke_wasm_extension_export(
    ext_id: str,
    export_name: str,
    payload: Mapping[str, Any] | None = None,
    *,
    user: Any | None = None,
    access_token: str | None = None,
    context: str = "user",
    owner_id: str | None = None,
) -> dict[str, Any]:
    extension = _get_registered_extension(ext_id)
    permissions = await _extension_permissions(extension)
    api = ExtensionHostAPI(
        extension.id,
        permissions,
        user_id=_user_id(user),
        access_token=access_token,
        context=context,
        owner_id=owner_id,
    )
    event_loop = asyncio.get_running_loop()

    return await asyncio.to_thread(
        _invoke_wasm_extension_export_sync,
        extension,
        export_name,
        payload or {},
        api,
        event_loop,
    )


def _invoke_wasm_extension_export_sync(
    extension: WasmExtension,
    export_name: str,
    payload: Mapping[str, Any],
    api: ExtensionHostAPI,
    event_loop: asyncio.AbstractEventLoop,
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
    add_extension_host_imports(linker, ExtensionAPIHost(api), event_loop)

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
