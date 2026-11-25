from __future__ import annotations

import asyncio
from time import perf_counter

from fastapi import FastAPI
from loguru import logger

from lnbits.core.db import core_app_extra
from lnbits.core.services.extensions import get_wasm_runtime_limits_for_extension
from lnbits.core.services.scheduler import scheduler
from lnbits.settings import settings

from ..wasm.component import warm_wasm_extension
from ..wasm.loader import WasmExtension, load_wasm_extension
from ..wasm.scheduler import register_wasm_schedule_handlers
from .api import (
    register_wasm_extension_api_routes,
    unregister_wasm_extension_api_routes,
)
from .assets import mount_wasm_extension_static
from .ui import register_wasm_extension_ui_routes


async def register_wasm_extension(app: FastAPI, ext_id: str) -> WasmExtension:
    load_started_at = perf_counter()
    loaded = load_wasm_extension(ext_id)
    limits = await get_wasm_runtime_limits_for_extension(ext_id)
    await asyncio.to_thread(warm_wasm_extension, loaded, limits)
    core_app_extra.wasm_extension_registry.require_available(loaded)
    module_size = _format_wasm_extension_size(loaded.module_path.stat().st_size)
    mount_wasm_extension_static(app, loaded)
    register_wasm_extension_ui_routes(app, loaded)
    register_wasm_extension_api_routes(app, loaded)

    core_app_extra.wasm_extension_registry.register(loaded)
    register_wasm_schedule_handlers(loaded)

    settings.activate_extension_paths(ext_id, [])
    load_seconds = perf_counter() - load_started_at
    logger.info(
        f"Loaded WASM extension '{loaded.id}' "
        f"({module_size}) in {load_seconds:.2f} s."
    )
    return loaded


def unregister_wasm_extension(app: FastAPI, ext_id: str) -> None:
    scheduler.unregister(f"extension:{ext_id}")
    routes_removed = unregister_wasm_extension_api_routes(app, ext_id)
    core_app_extra.wasm_extension_registry.unregister(ext_id)
    if routes_removed:
        logger.info(f"Unloaded WASM extension API routes for '{ext_id}'.")


def _format_wasm_extension_size(size_bytes: int) -> str:
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:,.2f} MB"
    return f"{size_bytes / 1_000:,.2f} KB"
