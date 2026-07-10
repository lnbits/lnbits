from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lnbits.core.wasm_ext.wasm.config import (
    WasmExtensionConfig,
    WasmExtensionExport,
    parse_wasm_extension_config,
)
from lnbits.settings import settings


@dataclass(frozen=True)
class WasmExtension:
    id: str
    name: str
    version: str
    root_path: Path
    module_path: Path
    wit_path: Path | None
    world: str
    exports: list[WasmExtensionExport]
    config: WasmExtensionConfig


def is_wasm_extension_id(ext_id: str) -> bool:
    ext_dir = Path(settings.lnbits_extensions_path, "extensions", ext_id)
    config = _load_json(ext_dir / "config.json")
    return bool(config and config.get("extension_type") == "wasm")


def is_wasm_extension_dir(ext_dir: Path) -> bool:
    config = _load_json(ext_dir / "config.json")
    return bool(config and config.get("extension_type") == "wasm")


def load_wasm_extension_config(ext_id: str) -> WasmExtensionConfig | None:
    ext_dir = Path(settings.lnbits_extensions_path, "extensions", ext_id)
    config = _load_json(ext_dir / "config.json")
    if not config or config.get("extension_type") != "wasm":
        return None
    return parse_wasm_extension_config(ext_id, config)


def load_wasm_extension(ext_id: str) -> WasmExtension:
    ext_dir = Path(settings.lnbits_extensions_path, "extensions", ext_id)
    raw_config = _load_json(ext_dir / "config.json")
    if not raw_config:
        raise FileNotFoundError(f"Missing WASM extension config for '{ext_id}'.")
    if raw_config.get("extension_type") != "wasm":
        raise ValueError(f"Extension '{ext_id}' is not a WASM extension.")
    config = parse_wasm_extension_config(ext_id, raw_config)

    module_path = _extension_path(ext_dir, config.wasm.module)
    wit_path = _optional_extension_path(ext_dir, config.wasm.wit)
    _check_wasm_module(module_path)
    if wit_path and not wit_path.is_file():
        raise FileNotFoundError(f"WIT file not found: {wit_path}")

    return WasmExtension(
        id=config.id,
        name=config.name,
        version=config.version,
        root_path=ext_dir,
        module_path=module_path,
        wit_path=wit_path,
        world=config.wasm.world,
        exports=config.wasm.exports,
        config=config,
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as config_file:
        value = json.load(config_file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in '{path}'.")
    return value


def _extension_path(ext_dir: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing relative path for extension '{ext_dir.name}'.")
    path = (ext_dir / value).resolve()
    if ext_dir.resolve() not in path.parents:
        raise ValueError(f"Extension path escapes extension root: {value}")
    return path


def _optional_extension_path(ext_dir: Path, value: Any) -> Path | None:
    if value is None:
        return None
    return _extension_path(ext_dir, value)


def _check_wasm_module(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"WASM module not found: {path}")
    with path.open("rb") as wasm_file:
        magic = wasm_file.read(4)
    if magic != b"\0asm":
        raise ValueError(f"Invalid WASM module: {path}")
