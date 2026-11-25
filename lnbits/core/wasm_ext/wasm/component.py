from __future__ import annotations

import platform
import subprocess
import sys
from contextlib import suppress
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

import psutil
from wasmtime import Engine, WasmtimeError, component

from lnbits.helpers import file_hash
from lnbits.settings import settings

from . import compiler
from .loader import WasmExtension


class WasmCompilationError(ValueError):
    pass


class _ExtensionEngine(Engine):
    def __init__(self, cache_dir: Path, stack_limit: int):
        super().__init__(compiler.engine_config(stack_limit))
        self.cache_dir = cache_dir
        self.stack_limit = stack_limit
        self.compile_lock = Lock()


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
def _wasm_engine(
    ext_id: str, max_wasm_stack_bytes: int | None = None
) -> _ExtensionEngine:
    cache_dir = Path(settings.lnbits_data_folder, "wasm_cache", ext_id).resolve()
    extensions_dir = settings.wasm_extensions_dir.resolve()
    if cache_dir.is_relative_to(extensions_dir) or extensions_dir.is_relative_to(
        cache_dir
    ):
        raise ValueError("WASM compiler cache must be outside the extension directory.")
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stack_limit = (
        settings.wasm_runtime_max_wasm_stack_bytes
        if max_wasm_stack_bytes is None
        else max_wasm_stack_bytes
    )
    return _ExtensionEngine(cache_dir, stack_limit)


def _wasm_component(
    extension: WasmExtension, engine: _ExtensionEngine
) -> component.Component:
    stat = extension.module_path.stat()
    return _cached_wasm_component(
        engine,
        str(extension.module_path),
        stat.st_mtime_ns,
        stat.st_size,
        stat.st_ctime_ns,
    )


@lru_cache(maxsize=32)
def _cached_wasm_component(
    engine: _ExtensionEngine,
    module_path: str,
    mtime_ns: int,
    size: int,
    ctime_ns: int = 0,
) -> component.Component:
    with engine.compile_lock:
        digest = file_hash(module_path)
        target = (
            f"{sys.platform}-{platform.machine()}-{version('wasmtime')}"
            f"-{engine.stack_limit}"
        )
        directory = engine.cache_dir / target
        directory.mkdir(mode=0o700, exist_ok=True)
        artifact = directory / f"{digest}.cwasm"
        if artifact.is_file():
            try:
                return component.Component.deserialize_file(engine, str(artifact))
            except WasmtimeError:
                # A changed CPU or engine configuration can invalidate a local build.
                pass

        with TemporaryDirectory(dir=directory) as staging:
            output = Path(staging, artifact.name)
            _run_compiler(engine, Path(module_path), output)
            # Only publish native code produced by our own successful worker.
            try:
                output.replace(artifact)
            except PermissionError:
                # Another Windows process may already have mapped the same build.
                if not artifact.is_file():
                    raise
        compiled = component.Component.deserialize_file(engine, str(artifact))
        with suppress(OSError):
            _trim_compiler_cache(engine.cache_dir, artifact)
        return compiled


def _run_compiler(engine: _ExtensionEngine, source: Path, output: Path) -> None:
    limit = settings.lnbits_wasm_compiler_memory_limit_mb * 1_000_000
    command = [sys.executable]
    if getattr(sys, "frozen", False):
        command.append("--wasm-compiler")
    else:
        command.extend(["-I", compiler.__file__])
    command.extend(
        [str(source), str(output), str(engine.cache_dir), str(engine.stack_limit)]
    )
    with subprocess.Popen(  # noqa: S603
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) as worker:
        try:
            process = psutil.Process(worker.pid)
            while settings.lnbits_running:
                if process.memory_info().rss > limit:
                    raise WasmCompilationError(
                        f"WASM compiler for '{engine.cache_dir.name}' exceeded its "
                        f"{limit // 1_000_000} MB memory limit."
                    )
                try:
                    worker.wait(timeout=0.025)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except psutil.NoSuchProcess:
            # The process exited between reading its PID and sampling RSS.
            worker.wait()
        except psutil.AccessDenied as exc:
            raise WasmCompilationError(
                f"Cannot monitor the WASM compiler for '{engine.cache_dir.name}'."
            ) from exc
        finally:
            if worker.poll() is None:
                worker.kill()
            worker.wait()
    if not settings.lnbits_running:
        raise WasmCompilationError("WASM compilation interrupted by shutdown.")
    if worker.returncode:
        raise WasmCompilationError(
            f"WASM compilation failed for '{engine.cache_dir.name}'."
        )


def _trim_compiler_cache(cache_dir: Path, current: Path) -> None:
    # Preserve the 512 MiB per-extension soft limit of the original Wasmtime cache.
    # Concurrent removals and files still mapped on Windows are harmless.
    remaining = 512 * 1024 * 1024 - current.stat().st_size
    entries = []
    for path in cache_dir.glob("*/*.cwasm"):
        if path != current:
            with suppress(FileNotFoundError):
                stat = path.stat()
                entries.append((stat.st_mtime_ns, path, stat.st_size))
    for _, path, size in sorted(entries, reverse=True):
        if size <= remaining:
            remaining -= size
        else:
            with suppress(FileNotFoundError, PermissionError):
                path.unlink()
