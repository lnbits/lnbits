"""Extension runtime contracts."""

from .api import (
    ExtensionAPI,
    ExtensionAPIMethod,
    extension_api_contract,
    extension_api_method,
    get_extension_api_method,
    list_extension_api_methods,
)
from .loader import WasmExtension, load_wasm_extension, register_wasm_extension
from .prototype import InMemoryExtensionAPI, InMemoryExtensionState
from .runtime import ExtensionAPIHost

__all__ = [
    "ExtensionAPI",
    "ExtensionAPIHost",
    "ExtensionAPIMethod",
    "InMemoryExtensionAPI",
    "InMemoryExtensionState",
    "WasmExtension",
    "extension_api_contract",
    "extension_api_method",
    "get_extension_api_method",
    "load_wasm_extension",
    "list_extension_api_methods",
    "register_wasm_extension",
]
