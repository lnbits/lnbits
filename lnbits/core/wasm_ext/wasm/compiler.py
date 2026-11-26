"""Standalone compiler entry point. Keep this independent of LNbits startup."""

import hashlib
import json
import sys
from pathlib import Path

from wasmtime import Config, Engine, component


def engine_config(stack_limit: int) -> Config:
    config = Config()
    config.wasm_component_model = True
    config.epoch_interruption = True
    config.consume_fuel = True
    config.parallel_compilation = False
    if stack_limit > 0:
        config.max_wasm_stack = stack_limit
    return config


def main() -> None:
    source, output, legacy_cache, stack = sys.argv[1:]
    config = engine_config(int(stack))
    # Existing installations may already have this build in Wasmtime's cache.
    if (Path(legacy_cache) / "modules").is_dir():
        cache_config = Path(output).with_suffix(".toml")
        cache_config.write_text(
            f"[cache]\ndirectory = {json.dumps(legacy_cache)}\n", encoding="utf-8"
        )
        config.cache = str(cache_config)
    wasm = Path(source).read_bytes()
    if hashlib.sha256(wasm).hexdigest() != Path(output).stem:
        raise ValueError("WASM source changed during compilation.")
    compiled = component.Component(Engine(config), wasm)
    Path(output).write_bytes(compiled.serialize())


if __name__ == "__main__":
    main()
