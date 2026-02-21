import asyncio
import json
import sys
from pathlib import Path

from lnbits.settings import settings

WASM_RUNNER = Path(__file__).with_name("runner.py")


class WasmExecutionError(RuntimeError):
    pass


def resolve_module_path(ext_id: str, upgrade_hash: str | None = None) -> Path:
    if upgrade_hash:
        ext_dir = Path(
            settings.lnbits_extensions_upgrade_path, f"{ext_id}-{upgrade_hash}"
        )
    else:
        ext_dir = Path(settings.lnbits_extensions_path, "extensions", ext_id)
    wasm_dir = ext_dir / "wasm"
    wasm_path = wasm_dir / "module.wasm"
    if wasm_path.exists():
        if (
            settings.lnbits_wasm_max_module_bytes > 0
            and wasm_path.stat().st_size > settings.lnbits_wasm_max_module_bytes
        ):
            raise WasmExecutionError("WASM module exceeds size limit.")
        return wasm_path
    wat_path = wasm_dir / "module.wat"
    if wat_path.exists():
        if (
            settings.lnbits_wasm_max_module_bytes > 0
            and wat_path.stat().st_size > settings.lnbits_wasm_max_module_bytes
        ):
            raise WasmExecutionError("WASM module exceeds size limit.")
        return wat_path
    raise WasmExecutionError(f"No wasm module found for extension '{ext_id}'.")


async def wasm_call(
    ext_id: str,
    function: str,
    args: list[int],
    timeout_s: float | None = None,
    upgrade_hash: str | None = None,
) -> int:
    module_path = resolve_module_path(ext_id, upgrade_hash)
    if timeout_s is None:
        timeout_s = settings.lnbits_wasm_timeout_seconds

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(WASM_RUNNER),
        str(module_path),
        ext_id,
        function,
        *[str(a) for a in args],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise WasmExecutionError("WASM execution timed out") from exc

    payload = {}
    if stdout:
        try:
            payload = json.loads(stdout.decode())
        except json.JSONDecodeError:
            payload = {}

    if proc.returncode != 0:
        detail = payload.get("error")
        if not detail and stderr:
            detail = stderr.decode().strip()
        if not detail:
            detail = "WASM runner error"
        raise WasmExecutionError(detail)

    if not payload:
        raise WasmExecutionError("Invalid WASM runner output")

    if not payload.get("ok"):
        raise WasmExecutionError(payload.get("error", "WASM execution failed"))

    return int(payload["result"])
