import os
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_mock.plugin import MockerFixture
from wasmtime import Store, component, wat2wasm

from lnbits.core.wasm_ext.wasm.component import (
    _cached_wasm_component,
    _wasm_engine,
)
from lnbits.settings import (
    ExtensionsSettings,
    Settings,
    UpdateSettings,
    WasmRuntimeLimits,
)


def test_compiler_memory_limit_is_a_global_admin_and_environment_setting(monkeypatch):
    field = "lnbits_wasm_compiler_memory_limit_mb"
    assert ExtensionsSettings.model_fields[field].default == 200
    assert field in UpdateSettings.model_fields
    assert field not in WasmRuntimeLimits.model_fields
    monkeypatch.setenv(field.upper(), "350")
    loaded = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert loaded.lnbits_wasm_compiler_memory_limit_mb == 350
    with pytest.raises(ValueError):
        UpdateSettings(lnbits_wasm_compiler_memory_limit_mb=0)


def test_wasm_compilation_cache_survives_restart_and_tracks_content(tmp_path: Path):
    data_dir = tmp_path / "data with spaces and 'quotes'"
    module_path = tmp_path / "extension.wasm"
    module_path.write_bytes(_component_bytes(7))

    assert _compile_in_process(data_dir, module_path) == 7
    cached = _cache_files(data_dir)
    assert len(cached) == 1
    original_stat = next(iter(cached)).stat()

    assert _compile_in_process(data_dir, module_path) == 7
    assert _cache_files(data_dir) == cached
    reused_stat = next(iter(cached)).stat()
    assert reused_stat.st_ino == original_stat.st_ino
    assert reused_stat.st_mtime_ns == original_stat.st_mtime_ns

    # Changing content must invalidate the disk cache even with unchanged metadata.
    module_stat = module_path.stat()
    module_path.write_bytes(_component_bytes(8))
    os.utime(module_path, ns=(module_stat.st_atime_ns, module_stat.st_mtime_ns))
    assert module_path.stat().st_size == module_stat.st_size
    assert _compile_in_process(data_dir, module_path) == 8
    assert len(_cache_files(data_dir)) == 2

    assert _compile_in_process(data_dir, module_path, "otherext") == 8
    assert len(_cache_files(data_dir, "otherext")) == 1
    assert len(_cache_files(data_dir)) == 2


def test_compiler_limit_stops_cold_build_but_allows_retry_and_cache_hits(
    tmp_path: Path, settings: Settings, mocker: MockerFixture
):
    mocker.patch.object(settings, "lnbits_data_folder", str(tmp_path))
    mocker.patch.object(settings, "lnbits_wasm_compiler_memory_limit_mb", 1)
    path = tmp_path / "extension.wasm"
    path.write_bytes(_component_bytes(7))
    engine = _wasm_engine("memorytest", 512 * 1024)
    stat = path.stat()
    args = (engine, str(path), stat.st_mtime_ns, stat.st_size)

    with pytest.raises(ValueError, match="memorytest.*1 MB memory limit"):
        _cached_wasm_component(*args)
    assert not _cache_files(tmp_path, "memorytest")

    settings.lnbits_wasm_compiler_memory_limit_mb = 200
    _cached_wasm_component(*args)
    _cached_wasm_component.cache_clear()
    settings.lnbits_wasm_compiler_memory_limit_mb = 1
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.component._run_compiler",
        side_effect=AssertionError("cache hit spawned a compiler"),
    )
    _cached_wasm_component(*args)


def test_wasm_component_remains_usable_after_engine_cache_eviction(
    tmp_path: Path, settings: Settings, mocker: MockerFixture
):
    mocker.patch.object(settings, "lnbits_data_folder", str(tmp_path))
    module_path = tmp_path / "extension.wasm"
    module_path.write_bytes(_component_bytes(7))
    stat = module_path.stat()
    _wasm_engine.cache_clear()
    try:
        # The ninth extension evicts the first engine; revisit that extension.
        for index in [*range(9), 0]:
            engine = _wasm_engine(f"ext{index}", 512 * 1024)
            compiled = _cached_wasm_component(
                engine, str(module_path), stat.st_mtime_ns, stat.st_size
            )
            store = Store(engine)
            store.set_fuel(10_000)
            store.set_epoch_deadline(1_000)
            instance = component.Linker(engine).instantiate(store, compiled)
            function = instance.get_func(store, "value")
            assert function is not None
            assert function(store) == 7
            function.post_return(store)
    finally:
        _cached_wasm_component.cache_clear()
        _wasm_engine.cache_clear()


def _component_bytes(value: int) -> bytearray:
    return wat2wasm(f"""(component
            (core module $m
                (func (export "value") (result i32) i32.const {value}))
            (core instance $i (instantiate $m))
            (func (export "value") (result s32)
                (canon lift (core func $i "value"))))""")


def _cache_files(data_dir: Path, ext_id: str = "demoext") -> set[Path]:
    return {
        path
        for path in (data_dir / "wasm_cache" / ext_id).glob("*/*.cwasm")
        if path.is_file()
    }


def _compile_in_process(
    data_dir: Path, module_path: Path, ext_id: str = "demoext"
) -> int:
    script = """
import sys
from pathlib import Path
from wasmtime import Store, component
from lnbits.core.wasm_ext.wasm.component import _cached_wasm_component, _wasm_engine

path = Path(sys.argv[1])
stat = path.stat()
stack_limit = 512 * 1024
engine = _wasm_engine(sys.argv[2], stack_limit)
compiled = _cached_wasm_component(
    engine, str(path), stat.st_mtime_ns, stat.st_size
)
store = Store(engine)
store.set_fuel(10_000)
store.set_epoch_deadline(1_000)
instance = component.Linker(engine).instantiate(store, compiled)
function = instance.get_func(store, "value")
assert function is not None
print(function(store))
function.post_return(store)
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, str(module_path), ext_id],
        env={**os.environ, "LNBITS_DATA_FOLDER": str(data_dir)},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return int(result.stdout.strip())
