from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI
from loguru import logger

from lnbits.core.db import core_app_extra
from lnbits.settings import settings

from ..wasm.component import warm_wasm_extension
from ..wasm.loader import WasmExtension, load_wasm_extension
from .api import (
    register_wasm_extension_api_routes,
    unregister_wasm_extension_api_routes,
)
from .assets import mount_wasm_extension_static
from .ui import register_wasm_extension_ui_routes


def register_wasm_extension(app: FastAPI, ext_id: str) -> WasmExtension:
    load_started_at = perf_counter()
    loaded = load_wasm_extension(ext_id)
    core_app_extra.wasm_extension_registry.require_available(loaded)

    warm_wasm_extension(loaded)
    mount_wasm_extension_static(app, loaded)
    register_wasm_extension_ui_routes(app, loaded)
    register_wasm_extension_api_routes(app, loaded)

    core_app_extra.wasm_extension_registry.register(loaded)

    settings.activate_extension_paths(ext_id, [])
    module_size = _format_wasm_extension_size(loaded.module_path.stat().st_size)
    load_seconds = perf_counter() - load_started_at
    logger.info(
        f"Loaded WASM extension '{loaded.id}' "
        f"({module_size}) in {load_seconds:.2f} s."
    )
    return loaded


def unregister_wasm_extension(app: FastAPI, ext_id: str) -> None:
    routes_removed = unregister_wasm_extension_api_routes(app, ext_id)
    core_app_extra.wasm_extension_registry.unregister(ext_id)
    if routes_removed:
        logger.info(f"Unloaded WASM extension API routes for '{ext_id}'.")


def _format_wasm_extension_size(size_bytes: int) -> str:
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:,.2f} MB"
    return f"{size_bytes / 1_000:,.2f} KB"
