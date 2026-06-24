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
from .wasm import invoke_wasm_extension_export

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
    "invoke_wasm_extension_export",
    "list_extension_api_methods",
    "load_wasm_extension",
    "register_wasm_extension",
]
