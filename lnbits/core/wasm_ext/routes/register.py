from __future__ import annotations

from fastapi import FastAPI
from loguru import logger

from lnbits.core.db import core_app_extra
from lnbits.settings import settings

from ..wasm.component import warm_wasm_extension
from ..wasm.loader import WasmExtension, load_wasm_extension
from .api import register_wasm_extension_api_routes
from .assets import mount_wasm_extension_static
from .ui import register_wasm_extension_ui_routes


def register_wasm_extension(app: FastAPI, ext_id: str) -> WasmExtension:
    loaded = load_wasm_extension(ext_id)
    core_app_extra.wasm_extension_registry.require_available(loaded)

    warm_wasm_extension(loaded)
    mount_wasm_extension_static(app, loaded)
    register_wasm_extension_ui_routes(app, loaded)
    register_wasm_extension_api_routes(app, loaded)

    core_app_extra.wasm_extension_registry.register(loaded)

    settings.activate_extension_paths(ext_id, "", [])
    logger.info(
        f"Loaded WASM extension '{loaded.id}' "
        f"({loaded.module_path.stat().st_size} bytes)."
    )
    return loaded
