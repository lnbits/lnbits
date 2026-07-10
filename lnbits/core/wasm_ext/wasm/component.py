from __future__ import annotations

from functools import lru_cache
from typing import Any

from wasmtime import Config, Engine

from lnbits.settings import settings

from .loader import WasmExtension


def warm_wasm_extension(extension: WasmExtension) -> None:
    _wasm_component(extension)


@lru_cache(maxsize=8)
def _wasm_engine(max_wasm_stack_bytes: int | None = None) -> Any:
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
    return Engine(config)


def _wasm_component(
    extension: WasmExtension,
    limits: dict[str, int] | None = None,
) -> Any:
    stat = extension.module_path.stat()
    max_wasm_stack_bytes = (
        limits["wasm_runtime_max_wasm_stack_bytes"]
        if limits
        else settings.wasm_runtime_max_wasm_stack_bytes
    )
    return _cached_wasm_component(
        str(extension.module_path),
        stat.st_mtime_ns,
        stat.st_size,
        max_wasm_stack_bytes,
    )


@lru_cache(maxsize=32)
def _cached_wasm_component(
    module_path: str,
    mtime_ns: int,
    size: int,
    max_wasm_stack_bytes: int,
) -> Any:
    from wasmtime import component

    return component.Component.from_file(
        _wasm_engine(max_wasm_stack_bytes), module_path
    )
