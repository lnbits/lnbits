from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from wasmtime import Config, Engine

from lnbits.settings import settings

from .loader import WasmExtension


def warm_wasm_extension(
    extension: WasmExtension, limits: dict[str, int] | None = None
) -> None:
    max_wasm_stack_bytes = (
        limits["wasm_runtime_max_wasm_stack_bytes"]
        if limits
        else settings.wasm_runtime_max_wasm_stack_bytes
    )
    _wasm_component(extension, _wasm_engine(extension.id, max_wasm_stack_bytes))


@lru_cache(maxsize=8)
def _wasm_engine(ext_id: str, max_wasm_stack_bytes: int | None = None) -> Any:
    config = Config()
    config.wasm_component_model = True
    config.epoch_interruption = True
    config.consume_fuel = True
    stack_limit = (
        settings.wasm_runtime_max_wasm_stack_bytes
        if max_wasm_stack_bytes is None
        else max_wasm_stack_bytes
    )
    if stack_limit > 0:
        config.max_wasm_stack = stack_limit

    cache_dir = Path(settings.lnbits_data_folder, "wasm_cache", ext_id).resolve()
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Wasmtime requires a TOML file; only the compiled cache needs to persist.
    with TemporaryDirectory() as config_dir:
        cache_config = Path(config_dir, "cache.toml")
        cache_config.write_text(
            f"[cache]\ndirectory = {json.dumps(str(cache_dir), ensure_ascii=False)}\n",
            encoding="utf-8",
        )
        config.cache = str(cache_config)
    return Engine(config)


def _wasm_component(extension: WasmExtension, engine: Engine) -> Any:
    stat = extension.module_path.stat()
    return _cached_wasm_component(
        engine,
        str(extension.module_path),
        stat.st_mtime_ns,
        stat.st_size,
    )


@lru_cache(maxsize=32)
def _cached_wasm_component(
    engine: Engine,
    module_path: str,
    mtime_ns: int,
    size: int,
) -> Any:
    from wasmtime import component

    return component.Component.from_file(engine, module_path)
