"""Supervised trusted workers. Draft code is only executed inside WASM."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

WORKERS = Path(__file__).with_name("studio_workers")
_environment_lock = asyncio.Lock()
BUILD_SLOTS = asyncio.Semaphore(1)


def worker_environment(data: Path) -> dict[str, str]:
    temporary = data / "tmp"
    temporary.mkdir(mode=0o700, exist_ok=True)
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "en_US.UTF-8",
        "HOME": str(temporary),
        "TMPDIR": str(temporary),
        "TEMP": str(temporary),
        "PYTHONUNBUFFERED": "1",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_CACHE_DIR": "1",
        "RAYON_NUM_THREADS": "2",
    }


async def ensure_worker(
    data: Path, kind: str, emit: Callable[[str], Awaitable[None]]
) -> Path:
    if sys.platform not in {"linux", "darwin"}:
        raise ValueError("Studio workers require Linux or macOS.")
    if kind == "agent" and sys.version_info < (3, 11):
        raise ValueError("Studio AI requires Python 3.11 or newer.")
    requirements = WORKERS / f"{kind}-requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()[:16]
    environment = data / f"{kind}-env-{digest}"
    python = environment / "bin" / "python"
    async with _environment_lock:
        if (environment / ".ready").is_file():
            return python
        await emit(f"Preparing the pinned {kind} environment…")
        await run_worker(
            [sys.executable, "-I", "-m", "venv", str(environment)], data, timeout=120
        )
        await run_worker(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--only-binary=:all:",
                "--index-url",
                "https://pypi.org/simple",
                "-r",
                str(requirements),
            ],
            data,
            timeout=300,
        )
        (environment / ".ready").touch(mode=0o600)
    return python


async def run_worker(
    command: list[str],
    data: Path,
    *,
    payload: dict | None = None,
    handle: Callable[[dict], Awaitable[dict | None]] | None = None,
    timeout: int = 180,
    scratch: Path | None = None,
) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=data,
        env=worker_environment(data),
        start_new_session=True,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        limit=2 * 1024 * 1024,
    )
    assert process.stdin and process.stdout
    writer, reader = process.stdin, process.stdout
    if payload is not None:
        writer.write(json.dumps(payload).encode() + b"\n")
        await writer.drain()

    async def consume() -> None:
        total = 0
        while line := await reader.readline():
            total += len(line)
            if total > 8 * 1024 * 1024:
                raise ValueError("Worker output limit exceeded.")
            if handle:
                result = await handle(json.loads(line))
                if result is not None:
                    writer.write(json.dumps(result).encode() + b"\n")
                    await writer.drain()
        if await process.wait():
            raise ValueError(
                "Worker failed. Check the source and configured model, then retry."
            )

    consumer = asyncio.create_task(consume())
    try:
        deadline = asyncio.get_running_loop().time() + timeout
        while not consumer.done():
            await _check_worker_limits(data, process.pid, deadline, scratch)
            await asyncio.wait({consumer}, timeout=0.25)
        await consumer
    finally:
        _kill_worker(process)
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        await process.wait()


def _kill_worker(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


async def _check_worker_limits(
    data: Path, pid: int, deadline: float, scratch: Path | None
) -> None:
    if (data / "stop").exists():
        raise ValueError("Stopped. Partial edits remain available for review or Undo.")
    if asyncio.get_running_loop().time() > deadline:
        raise ValueError("Worker time limit exceeded.")
    await _check_memory(pid)
    if scratch:
        size = await asyncio.to_thread(_disk_usage, scratch)
        # The compiler's embedded libraries and bindings are also guest-writable.
        size += await asyncio.to_thread(_disk_usage, data / "tmp")
        if size > 256 * 1024 * 1024:
            raise ValueError("Build disk limit exceeded.")


async def _check_memory(pid: int) -> None:
    # RSS supervision works on both supported platforms, unlike macOS RLIMIT_AS.
    if sys.platform == "linux":
        try:
            pages = (
                await asyncio.to_thread(Path(f"/proc/{pid}/statm").read_text)
            ).split()[1]
        except FileNotFoundError:
            return
        if int(pages) * os.sysconf("SC_PAGE_SIZE") > 2 * 1024**3:
            raise ValueError("Worker memory limit exceeded (2 GiB).")
        return
    probe = await asyncio.create_subprocess_exec(
        "/bin/ps",
        "-o",
        "rss=",
        "-p",
        str(pid),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    output, _ = await probe.communicate()
    if output.strip() and int(output.strip()) > 2 * 1024 * 1024:
        raise ValueError("Worker memory limit exceeded (2 GiB).")


def _disk_usage(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            total += path.lstat().st_size
        except FileNotFoundError:
            # Compiler temporary files can disappear during supervision.
            continue
    return total
