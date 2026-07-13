from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from wasmtime import Store, WasiConfig, component

from lnbits.core.crud.extensions import get_installed_extension
from lnbits.core.db import core_app_extra
from lnbits.settings import settings

from ..api.host import ExtensionHostAPI
from ..api.runtime import ExtensionAPIHost
from .component import _wasm_component, _wasm_engine
from .host import add_extension_host_imports
from .loader import WasmExtension

_WASM_EPOCH_DEADLINE_TICKS = 1_000_000_000
_WASM_UNLIMITED_FUEL = 2**63 - 1


async def invoke_wasm_extension_export(
    ext_id: str,
    export_name: str,
    payload: Mapping[str, Any] | None = None,
    *,
    user: Any | None = None,
    access_token: str | None = None,
    context: str = "user",
    owner_id: str | None = None,
    trigger_type: str = "unknown",
    request_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    event_type: str | None = None,
    wallet_id: str | None = None,
    payment_hash: str | None = None,
    checking_id: str | None = None,
    request_bytes: int | None = None,
    context_data: dict | None = None,
) -> dict[str, Any]:
    from lnbits.core.services.extensions import (
        finish_wasm_invocation,
        get_wasm_invocation_stop_reason,
        resolve_wasm_runtime_limits,
        start_wasm_invocation,
        stop_wasm_invocation,
        wasm_invocation_stop_requested,
    )

    extension = _get_registered_extension(ext_id)
    installed_extension = await _active_installed_extension(extension)
    permissions = installed_extension.permissions
    limits = resolve_wasm_runtime_limits(installed_extension)
    payload = payload or {}
    payload_size = _json_size(payload)
    effective_request_bytes = (
        request_bytes if request_bytes is not None else payload_size
    )
    _check_wasm_request_size(effective_request_bytes, limits)
    invocation = await start_wasm_invocation(
        extension_id=extension.id,
        export_name=export_name,
        trigger_type=trigger_type,
        user_id=_user_id(user) or owner_id,
        wallet_id=wallet_id,
        request_id=request_id,
        method=method,
        path=path,
        event_type=event_type,
        payment_hash=payment_hash,
        checking_id=checking_id,
        request_bytes=effective_request_bytes,
        context={"host_context": context, **(context_data or {})},
        runtime_limits=limits,
    )
    api = ExtensionHostAPI(
        extension.id,
        permissions,
        user_id=_user_id(user),
        access_token=access_token,
        context=context,
        owner_id=owner_id,
        wallet_id=wallet_id,
        invocation_id=invocation.id,
        runtime_limits=limits,
    )
    event_loop = asyncio.get_running_loop()
    thread_task = asyncio.create_task(
        asyncio.to_thread(
            _invoke_wasm_extension_export_sync,
            extension,
            export_name,
            payload,
            api,
            event_loop,
            invocation.id,
            limits,
        )
    )
    max_execution_ms = limits["wasm_runtime_max_execution_ms"]
    timed_out = False
    finished = False

    try:
        try:
            if max_execution_ms > 0:
                result = await asyncio.wait_for(
                    asyncio.shield(thread_task),
                    timeout=max_execution_ms / 1000,
                )
            else:
                result = await thread_task
        except asyncio.TimeoutError as exc:
            timed_out = True
            stop_reason = "WASM execution time limit exceeded."
            await stop_wasm_invocation(invocation.id, reason=stop_reason)
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(thread_task),
                    timeout=2,
                )
            except asyncio.TimeoutError:
                await finish_wasm_invocation(
                    invocation.id,
                    status="timeout",
                    error_type="TimeoutError",
                    error_message=stop_reason,
                    stop_reason=stop_reason,
                )
                finished = True
                raise TimeoutError(stop_reason) from exc

        status = (
            "timeout"
            if timed_out
            else (
                "stopped"
                if wasm_invocation_stop_requested(invocation.id)
                else "completed"
            )
        )
        await finish_wasm_invocation(
            invocation.id,
            status=status,
            response_bytes=_json_size(result),
            stop_reason=get_wasm_invocation_stop_reason(invocation.id),
        )
        finished = True
        return result
    except Exception as exc:
        if not finished:
            await finish_wasm_invocation(
                invocation.id,
                status=(
                    "timeout"
                    if timed_out
                    else (
                        "stopped"
                        if wasm_invocation_stop_requested(invocation.id)
                        else "failed"
                    )
                ),
                error_type=exc.__class__.__name__,
                error_message=str(exc),
                stop_reason=get_wasm_invocation_stop_reason(invocation.id),
            )
        raise


def _invoke_wasm_extension_export_sync(
    extension: WasmExtension,
    export_name: str,
    payload: Mapping[str, Any],
    api: ExtensionHostAPI,
    event_loop: asyncio.AbstractEventLoop,
    invocation_id: str,
    limits: dict[str, int],
) -> dict[str, Any]:
    from lnbits.core.services.extensions import attach_wasm_invocation_runtime

    engine = _wasm_engine(limits["wasm_runtime_max_wasm_stack_bytes"])
    store = Store(engine)
    _set_store_limits(store, limits)
    _set_store_fuel(store, limits)
    store.set_epoch_deadline(_WASM_EPOCH_DEADLINE_TICKS)
    attach_wasm_invocation_runtime(invocation_id, engine=engine, store=store)
    store.set_wasi(WasiConfig())

    linker = component.Linker(engine)
    linker.add_wasip2()
    add_extension_host_imports(linker, ExtensionAPIHost(api), event_loop)

    wasm_component = _wasm_component(extension, limits)
    instance = linker.instantiate(store, wasm_component)
    function = instance.get_func(store, export_name)
    if not function:
        raise KeyError(
            f"WASM extension '{extension.id}' has no export '{export_name}'."
        )

    result = function(store, json.dumps(payload))
    function.post_return(store)
    return _parse_wasm_export_result(result, limits)


def _parse_wasm_export_result(value: Any, limits: dict[str, int]) -> dict[str, Any]:
    if isinstance(value, bytes):
        value = value.decode()
    if not isinstance(value, str):
        return {"ok": True, "data": value}

    max_response_bytes = limits["wasm_runtime_max_response_bytes"]
    if max_response_bytes > 0:
        response_size = len(value.encode())
        if response_size > max_response_bytes:
            raise ValueError(
                f"WASM extension response is too large: {response_size} bytes."
            )

    parsed = json.loads(value)
    if isinstance(parsed, dict):
        return parsed
    return {"ok": True, "data": parsed}


def _get_registered_extension(ext_id: str) -> WasmExtension:
    extension = core_app_extra.wasm_extension_registry.get(ext_id)
    if extension:
        return extension
    raise RuntimeError(f"WASM extension '{ext_id}' is not registered.")


async def _active_installed_extension(extension: WasmExtension) -> Any:
    installed_extension = await get_installed_extension(extension.id)
    if (
        not installed_extension
        or settings.lnbits_extensions_deactivate_all
        or not installed_extension.active
    ):
        raise PermissionError(f"WASM extension '{extension.id}' is deactivated.")
    return installed_extension


def _user_id(user: Any | None) -> str | None:
    return getattr(user, "id", None) if user else None


def _set_store_limits(store: Any, limits: dict[str, int]) -> None:
    store.set_limits(
        memory_size=_wasm_limit(limits["wasm_runtime_max_memory_bytes"]),
        table_elements=_wasm_limit(limits["wasm_runtime_max_table_elements"]),
        instances=_wasm_limit(limits["wasm_runtime_max_instances"]),
        tables=_wasm_limit(limits["wasm_runtime_max_tables"]),
        memories=_wasm_limit(limits["wasm_runtime_max_memories"]),
    )


def _set_store_fuel(store: Any, limits: dict[str, int]) -> None:
    store.set_fuel(
        limits["wasm_runtime_max_fuel"]
        if limits["wasm_runtime_max_fuel"] > 0
        else _WASM_UNLIMITED_FUEL
    )


def _check_wasm_request_size(request_bytes: int, limits: dict[str, int]) -> None:
    max_request_bytes = limits["wasm_runtime_max_request_bytes"]
    if max_request_bytes > 0 and request_bytes > max_request_bytes:
        raise ValueError(f"WASM extension request is too large: {request_bytes} bytes.")


def _wasm_limit(value: int) -> int:
    return value if value > 0 else -1


def _json_size(value: Any) -> int:
    return len(json.dumps(value, default=str).encode())
