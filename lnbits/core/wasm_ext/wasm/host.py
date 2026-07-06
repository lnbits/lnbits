from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from typing import Any

from ..api.host import list_extension_api_methods
from ..api.runtime import ExtensionAPIHost


def add_extension_host_imports(
    linker: Any,
    api_host: ExtensionAPIHost,
    event_loop: asyncio.AbstractEventLoop,
) -> None:
    with linker.root() as root:
        methods_by_interface: dict[str, list[Any]] = {}
        for method in list_extension_api_methods():
            methods_by_interface.setdefault(method.host_interface, []).append(method)

        for host_interface, methods in methods_by_interface.items():
            with root.add_instance(f"lnbits:extension/{host_interface}") as host:
                for method in methods:
                    host.add_func(
                        method.host_name.replace("_", "-"),
                        _make_host_import(api_host, method.method_id, event_loop),
                    )


def _make_host_import(
    api_host: ExtensionAPIHost,
    host_name: str,
    event_loop: asyncio.AbstractEventLoop,
) -> Any:
    def host_import(_store: Any, request: Any = None) -> Any:
        payload = _component_payload_to_dict(request)
        future = asyncio.run_coroutine_threadsafe(
            api_host.invoke(host_name, payload), event_loop
        )
        response = future.result()
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


def _camel_to_kebab(value: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value).replace("_", "-").lower()
