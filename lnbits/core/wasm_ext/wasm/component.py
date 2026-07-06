from __future__ import annotations

from functools import lru_cache
from typing import Any

from .loader import WasmExtension


def warm_wasm_extension(extension: WasmExtension) -> None:
    _wasm_component(extension)


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
