import asyncio
import importlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from loguru import logger

from lnbits.core import core_app_extra
from lnbits.core.crud import (
    create_installed_extension,
    delete_installed_extension,
    get_db_version,
    get_installed_extension,
    get_installed_extensions_count,
    update_installed_extension_state,
)
from lnbits.core.crud.extensions import (
    create_wasm_invocation,
    delete_old_wasm_invocations,
    get_installed_extensions,
    get_wasm_invocation,
    mark_stale_wasm_invocations,
    update_installed_extension,
    update_installed_extension_wasm_runtime_limits,
    update_wasm_invocation,
)
from lnbits.core.crud.extensions import (
    get_wasm_invocation_stats as get_wasm_invocation_stats_crud,
)
from lnbits.core.crud.extensions import (
    get_wasm_invocations as get_wasm_invocations_crud,
)
from lnbits.core.helpers import migrate_extension_database
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.wasm.loader import is_wasm_extension_id
from lnbits.db import Connection
from lnbits.settings import WasmRuntimeLimits, settings

from ..models.extensions import (
    Extension,
    ExtensionMeta,
    ExtensionPermission,
    InstallableExtension,
    WasmInvocation,
    WasmInvocationStats,
)

_WASM_INVOCATION_CLEANUP_INTERVAL = timedelta(hours=1)
WASM_RUNTIME_LIMIT_FIELDS = tuple(WasmRuntimeLimits.__fields__.keys())


@dataclass
class WasmInvocationHandle:
    invocation: WasmInvocation
    engine: Any | None = None
    store: Any | None = None
    runtime_limits: dict[str, int] | None = None
    stop_requested: bool = False
    stop_reason: str | None = None


_wasm_invocation_lock = RLock()
_wasm_invocation_ready_lock = asyncio.Lock()
_wasm_invocation_handles: dict[str, WasmInvocationHandle] = {}
_wasm_invocations_marked_stale = False
_wasm_invocations_last_cleanup_at: datetime | None = None


def wasm_runtime_limit_defaults() -> dict[str, int]:
    return {field: int(getattr(settings, field)) for field in WASM_RUNTIME_LIMIT_FIELDS}


def validate_wasm_runtime_limit_overrides(
    limits: Mapping[str, Any] | None,
    *,
    strict: bool = True,
) -> dict[str, int]:
    if not limits:
        return {}

    validated: dict[str, int] = {}
    for field, raw_value in limits.items():
        if field not in WASM_RUNTIME_LIMIT_FIELDS:
            if strict:
                raise ValueError(f"Unknown WASM runtime limit field '{field}'.")
            continue

        value = _validate_wasm_runtime_limit_value(field, raw_value, strict=strict)
        if value is None:
            continue
        validated[field] = value

    return validated


def _validate_wasm_runtime_limit_value(
    field: str,
    raw_value: Any,
    *,
    strict: bool,
) -> int | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, bool):
        return _invalid_wasm_runtime_limit(field, strict, "must be an integer")
    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            return None
        if not raw_value.isdecimal():
            return _invalid_wasm_runtime_limit(field, strict, "must be an integer")
    if isinstance(raw_value, float) and not raw_value.is_integer():
        return _invalid_wasm_runtime_limit(field, strict, "must be an integer")

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        return _invalid_wasm_runtime_limit(
            field,
            strict,
            "must be an integer",
            exc=exc,
        )
    if value < 0:
        return _invalid_wasm_runtime_limit(field, strict, "cannot be negative")
    return value


def _invalid_wasm_runtime_limit(
    field: str,
    strict: bool,
    message: str,
    *,
    exc: Exception | None = None,
) -> None:
    if not strict:
        return None
    error = ValueError(f"WASM runtime limit '{field}' {message}.")
    if exc:
        raise error from exc
    raise error


def resolve_wasm_runtime_limits(
    installed_extension: InstallableExtension | None = None,
) -> dict[str, int]:
    limits = wasm_runtime_limit_defaults()
    if installed_extension:
        limits.update(
            validate_wasm_runtime_limit_overrides(
                installed_extension.wasm_runtime_limits,
                strict=False,
            )
        )
    return limits


async def get_wasm_runtime_limits_for_extension(ext_id: str) -> dict[str, int]:
    installed_extension = await get_installed_extension(ext_id)
    return resolve_wasm_runtime_limits(installed_extension)


async def update_wasm_extension_runtime_limits(
    ext_id: str,
    limits: Mapping[str, Any] | None,
) -> dict[str, int]:
    installed_extension = await get_installed_extension(ext_id)
    if not installed_extension:
        raise ValueError(f"Extension '{ext_id}' is not installed.")
    if not installed_extension.is_wasm:
        raise ValueError(f"Extension '{ext_id}' is not a WASM extension.")

    validated_limits = validate_wasm_runtime_limit_overrides(limits)
    await update_installed_extension_wasm_runtime_limits(
        ext_id=ext_id,
        limits=validated_limits,
    )
    return validated_limits


async def install_extension(
    ext_info: InstallableExtension,
    skip_download: bool | None = False,
    granted_permissions: list[ExtensionPermission] | None = None,
) -> Extension:

    ext_info.meta = ext_info.meta or ExtensionMeta()

    if (
        ext_info.meta.installed_release
        and not ext_info.meta.installed_release.is_version_compatible
    ):
        raise ValueError("Incompatible extension version")

    installed_ext = await get_installed_extension(ext_info.id)
    if installed_ext and installed_ext.meta:
        ext_info.meta.payments = installed_ext.meta.payments
    if installed_ext:
        ext_info.wasm_runtime_limits = installed_ext.wasm_runtime_limits

    await check_extensions_limit(installed_ext)

    if not skip_download:
        await ext_info.download_archive()

    extension_config = ext_info.load_archive_config()
    ext_info.permissions = validate_wasm_extension_permissions(
        ext_info, granted_permissions, extension_config
    )

    ext_info.extract_archive()

    db_version = await get_db_version(ext_info.id)
    await migrate_extension_database(ext_info, db_version)

    # if the extensions does not exist in the installed extensions table, create it
    # if it does exist, it will be activated later in the code
    if not installed_ext:
        await create_installed_extension(ext_info)
    else:
        await update_installed_extension(ext_info)

    extension = Extension.from_installable_ext(ext_info)
    if extension.is_upgrade_extension:
        # call stop while the old routes are still active
        await stop_extension_background_work(ext_info.id)

    if not extension.is_wasm:
        await start_extension_background_work(ext_info.id)

    return extension


async def check_extensions_limit(installed_ext: InstallableExtension | None = None):
    if settings.lnbits_max_extensions == 0 or installed_ext:
        return

    extensions_count = await get_installed_extensions_count()
    if extensions_count >= settings.lnbits_max_extensions:
        raise ValueError("Max amount of extensions have been installed")


async def ensure_wasm_invocation_monitoring_ready() -> None:
    global _wasm_invocations_last_cleanup_at, _wasm_invocations_marked_stale

    async with _wasm_invocation_ready_lock:
        now = _now()
        if not _wasm_invocations_marked_stale:
            await mark_stale_wasm_invocations()
            _wasm_invocations_marked_stale = True

        if (
            _wasm_invocations_last_cleanup_at is None
            or now - _wasm_invocations_last_cleanup_at
            >= _WASM_INVOCATION_CLEANUP_INTERVAL
        ):
            _wasm_invocations_last_cleanup_at = now
            await delete_old_wasm_invocations(
                settings.lnbits_wasm_invocation_retention_days
            )


async def start_wasm_invocation(
    *,
    extension_id: str,
    export_name: str,
    trigger_type: str = "unknown",
    user_id: str | None = None,
    wallet_id: str | None = None,
    request_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    event_type: str | None = None,
    payment_hash: str | None = None,
    checking_id: str | None = None,
    request_bytes: int | None = None,
    context: dict | None = None,
    runtime_limits: dict[str, int] | None = None,
) -> WasmInvocation:
    await ensure_wasm_invocation_monitoring_ready()
    _check_wasm_invocation_concurrency(
        extension_id=extension_id,
        user_id=user_id,
        limits=runtime_limits,
    )

    invocation = WasmInvocation(
        id=uuid4().hex,
        extension_id=extension_id,
        export_name=export_name,
        trigger_type=trigger_type,
        user_id=user_id,
        wallet_id=wallet_id,
        request_id=request_id,
        method=method,
        path=path,
        event_type=event_type,
        payment_hash=payment_hash,
        checking_id=checking_id,
        request_bytes=request_bytes,
        context=_safe_wasm_invocation_context(context or {}),
    )
    await create_wasm_invocation(invocation)

    with _wasm_invocation_lock:
        _wasm_invocation_handles[invocation.id] = WasmInvocationHandle(
            invocation,
            runtime_limits=runtime_limits,
        )

    return invocation


def attach_wasm_invocation_runtime(
    invocation_id: str,
    *,
    engine: Any,
    store: Any,
) -> None:
    with _wasm_invocation_lock:
        handle = _wasm_invocation_handles.get(invocation_id)
        if not handle:
            return
        handle.engine = engine
        handle.store = store
        if handle.stop_requested:
            _interrupt_wasm_invocation(handle)


def record_wasm_invocation_host_call(
    invocation_id: str | None,
    method_id: str,
) -> None:
    if not invocation_id:
        return

    with _wasm_invocation_lock:
        handle = _wasm_invocation_handles.get(invocation_id)
        if not handle:
            return

        invocation = handle.invocation
        invocation.host_call_count += 1
        category = _wasm_host_call_category(method_id)
        if category == "http":
            invocation.http_call_count += 1
        elif category == "storage":
            invocation.storage_call_count += 1
        elif category == "wallet":
            invocation.wallet_call_count += 1

        _check_wasm_host_call_limit(invocation, category, handle.runtime_limits)


async def stop_wasm_invocation(
    invocation_id: str,
    *,
    reason: str = "Stopped by admin.",
) -> bool:
    interrupted = False
    with _wasm_invocation_lock:
        handle = _wasm_invocation_handles.get(invocation_id)
        if handle:
            handle.stop_requested = True
            handle.stop_reason = reason
            handle.invocation.stop_reason = reason
            interrupted = _interrupt_wasm_invocation(handle)

    invocation = await get_wasm_invocation(invocation_id)
    if invocation and invocation.status == "running":
        invocation.stop_reason = reason
        await update_wasm_invocation(invocation)

    return interrupted


async def stop_wasm_extension_invocations(
    extension_id: str,
    *,
    reason: str = "Extension deactivated.",
) -> int:
    with _wasm_invocation_lock:
        invocation_ids = [
            invocation_id
            for invocation_id, handle in _wasm_invocation_handles.items()
            if handle.invocation.extension_id == extension_id
        ]

    for invocation_id in invocation_ids:
        await stop_wasm_invocation(invocation_id, reason=reason)

    return len(invocation_ids)


def wasm_invocation_stop_requested(invocation_id: str) -> bool:
    with _wasm_invocation_lock:
        handle = _wasm_invocation_handles.get(invocation_id)
        return bool(handle and handle.stop_requested)


def get_wasm_invocation_stop_reason(invocation_id: str) -> str | None:
    with _wasm_invocation_lock:
        handle = _wasm_invocation_handles.get(invocation_id)
        return handle.stop_reason if handle else None


async def finish_wasm_invocation(
    invocation_id: str,
    *,
    status: str,
    response_bytes: int | None = None,
    memory_peak_bytes: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    stop_reason: str | None = None,
) -> None:
    with _wasm_invocation_lock:
        handle = _wasm_invocation_handles.pop(invocation_id, None)

    invocation = (
        handle.invocation if handle else await get_wasm_invocation(invocation_id)
    )
    if not invocation:
        return

    reason = stop_reason or (handle.stop_reason if handle else None)
    if handle and handle.stop_requested and status == "failed":
        status = "stopped"
        reason = reason or "Stopped by admin."

    finished_at = _now()
    invocation.status = status
    invocation.finished_at = finished_at
    invocation.duration_ms = max(
        0, int((finished_at - invocation.started_at).total_seconds() * 1000)
    )
    invocation.response_bytes = response_bytes
    invocation.memory_peak_bytes = memory_peak_bytes
    invocation.error_type = error_type
    invocation.error_message = _safe_wasm_error_message(error_message)
    invocation.stop_reason = reason

    await update_wasm_invocation(invocation)


def get_current_wasm_invocations(
    extension_id: str | None = None,
) -> list[WasmInvocation]:
    with _wasm_invocation_lock:
        invocations = []
        for handle in _wasm_invocation_handles.values():
            if extension_id and handle.invocation.extension_id != extension_id:
                continue
            invocation = handle.invocation.copy(deep=True)
            if handle.stop_requested and invocation.status == "running":
                invocation.status = "stopping"
                invocation.stop_reason = handle.stop_reason
            invocations.append(invocation)

    return sorted(
        invocations, key=lambda invocation: invocation.started_at, reverse=True
    )


def _check_wasm_invocation_concurrency(
    *,
    extension_id: str,
    user_id: str | None,
    limits: dict[str, int] | None,
) -> None:
    if not limits:
        return

    with _wasm_invocation_lock:
        handles = list(_wasm_invocation_handles.values())
        if _wasm_limit_exceeded(
            limits["wasm_runtime_max_concurrent_invocations"],
            len(handles) + 1,
        ):
            raise ValueError("WASM runtime has too many active invocations.")

        extension_invocations = sum(
            1 for handle in handles if handle.invocation.extension_id == extension_id
        )
        if _wasm_limit_exceeded(
            limits["wasm_runtime_max_concurrent_invocations_per_extension"],
            extension_invocations + 1,
        ):
            raise ValueError(
                f"WASM extension '{extension_id}' has too many active invocations."
            )

        if not user_id:
            return

        user_invocations = sum(
            1 for handle in handles if handle.invocation.user_id == user_id
        )
        if _wasm_limit_exceeded(
            limits["wasm_runtime_max_concurrent_invocations_per_user"],
            user_invocations + 1,
        ):
            raise ValueError("WASM user has too many active invocations.")


def _check_wasm_host_call_limit(
    invocation: WasmInvocation,
    category: str,
    limits: dict[str, int] | None,
) -> None:
    if not limits:
        return

    if _wasm_limit_exceeded(
        limits["wasm_runtime_max_host_calls"],
        invocation.host_call_count,
    ):
        raise ValueError("WASM host call limit exceeded.")

    category_limits = {
        "http": (
            limits["wasm_runtime_max_http_calls"],
            invocation.http_call_count,
        ),
        "storage": (
            limits["wasm_runtime_max_storage_calls"],
            invocation.storage_call_count,
        ),
        "wallet": (
            limits["wasm_runtime_max_wallet_calls"],
            invocation.wallet_call_count,
        ),
    }
    category_limit = category_limits.get(category)
    if category_limit and _wasm_limit_exceeded(*category_limit):
        raise ValueError(f"WASM {category} host call limit exceeded.")


def _wasm_limit_exceeded(limit: int, value: int) -> bool:
    return limit > 0 and value > limit


async def get_wasm_invocation_history(
    *,
    extension_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[WasmInvocation]:
    await ensure_wasm_invocation_monitoring_ready()
    return await get_wasm_invocations_crud(
        extension_id=extension_id,
        status=status,
        limit=limit,
        offset=offset,
    )


async def get_wasm_invocation_summary(
    *,
    extension_id: str | None = None,
    hours: int = 24,
) -> WasmInvocationStats:
    await ensure_wasm_invocation_monitoring_ready()
    since = _now() - timedelta(hours=max(1, min(hours, 24 * 30)))
    return await get_wasm_invocation_stats_crud(
        extension_id=extension_id,
        since=since,
    )


def _interrupt_wasm_invocation(handle: WasmInvocationHandle) -> bool:
    if not handle.store or not handle.engine:
        return False
    try:
        handle.store.set_epoch_deadline(1)
        handle.engine.increment_epoch()
        return True
    except Exception as exc:
        logger.warning(
            f"Failed to interrupt WASM invocation '{handle.invocation.id}': {exc}"
        )
        return False


def _wasm_host_call_category(method_id: str) -> str:
    if method_id.startswith("http.") or method_id.startswith("extension.api."):
        return "http"
    if method_id.startswith("storage."):
        return "storage"
    if method_id.startswith("wallet."):
        return "wallet"
    return "host"


def _safe_wasm_invocation_context(context: dict) -> dict:
    safe_context: dict = {}
    for key, value in context.items():
        if not isinstance(key, str):
            continue
        if value is None or isinstance(value, (bool, int, float)):
            safe_context[key[:64]] = value
        elif isinstance(value, str):
            safe_context[key[:64]] = value[:256]
    return safe_context


def _safe_wasm_error_message(message: str | None) -> str | None:
    if not message:
        return None

    safe_message = message[:500]
    redactions = [
        (
            r"(?i)(api[-_ ]?key|token|authorization|password|secret|preimage)"
            r"\s*[:=]\s*[^\s,;]+",
            r"\1=[redacted]",
        ),
        (r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]"),
        (r"\b[a-fA-F0-9]{64}\b", "[redacted-hex]"),
    ]
    for pattern, replacement in redactions:
        safe_message = re.sub(pattern, replacement, safe_message)
    return safe_message


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def uninstall_extension(ext_id: str):
    await stop_extension_background_work(ext_id)

    settings.deactivate_extension_paths(ext_id)

    extension = await get_installed_extension(ext_id)
    if extension:
        extension.clean_extension_files()
    await delete_installed_extension(ext_id=ext_id)


async def activate_extension(ext: Extension):
    if ext.is_wasm:
        core_app_extra.register_new_wasm_ext_routes(ext.code)
        await update_installed_extension_state(ext_id=ext.code, active=True)
        return

    core_app_extra.register_new_ext_routes(ext)
    await update_installed_extension_state(ext_id=ext.code, active=True)
    await start_extension_background_work(ext.code)


async def deactivate_extension(ext_id: str):
    if is_wasm_extension_id(ext_id):
        await stop_wasm_extension_invocations(ext_id, reason="Extension deactivated.")
    settings.deactivate_extension_paths(ext_id)
    await update_installed_extension_state(ext_id=ext_id, active=False)
    await stop_extension_background_work(ext_id)


async def stop_extension_background_work(ext_id: str) -> bool:
    """
    Stop background work for extension (like asyncio.Tasks, WebSockets, etc).
    Extension must expose a `myextension_stop()` function if it is starting tasks.
    """
    if is_wasm_extension_id(ext_id):
        return True

    upgrade_hash = settings.extension_upgrade_hash(ext_id)
    ext = Extension(code=ext_id, is_valid=True, upgrade_hash=upgrade_hash)

    try:
        logger.info(f"Stopping background work for extension '{ext.module_name}'.")
        old_module = importlib.import_module(ext.module_name)

        stop_fn_name = f"{ext_id}_stop"
        if not hasattr(old_module, stop_fn_name):
            raise ValueError(f"No stop function found for '{ext.module_name}'.")

        stop_fn = getattr(old_module, stop_fn_name)
        if stop_fn:
            if asyncio.iscoroutinefunction(stop_fn):
                await stop_fn()
            else:
                stop_fn()
        logger.info(f"Stopped background work for extension '{ext.module_name}'.")
    except Exception as ex:
        logger.warning(f"Failed to stop background work for '{ext.module_name}'.")
        logger.warning(ex)
        return False

    return True


async def start_extension_background_work(ext_id: str) -> bool:
    """
    Start background work for extension (like asyncio.Tasks, WebSockets, etc).
    Extension CAN expose a `myextension_start()` function if it is starting tasks.
    Extension MUST expose a `myextension_stop()` in that case.
    """
    if is_wasm_extension_id(ext_id):
        return False

    upgrade_hash = settings.extension_upgrade_hash(ext_id)
    ext = Extension(code=ext_id, is_valid=True, upgrade_hash=upgrade_hash)

    try:
        logger.info(f"Starting background work for extension '{ext.module_name}'.")
        new_module = importlib.import_module(ext.module_name)
        start_fn_name = f"{ext_id}_start"

        # start function is optional, return False if not found
        if not hasattr(new_module, start_fn_name):
            return False

        start_fn = getattr(new_module, start_fn_name)
        if start_fn:
            if asyncio.iscoroutinefunction(start_fn):
                await start_fn()
            else:
                start_fn()
        logger.info(f"Started background work for extension '{ext.module_name}'.")
        return True
    except Exception as ex:
        logger.warning(f"Failed to start background work for '{ext.module_name}'.")
        logger.warning(ex)
        return False


async def get_valid_extensions(
    include_deactivated: bool | None = True, conn: Connection | None = None
) -> list[Extension]:
    installed_extensions = await get_installed_extensions(conn=conn)
    valid_extensions = [Extension.from_installable_ext(e) for e in installed_extensions]

    if include_deactivated:
        return valid_extensions

    if settings.lnbits_extensions_deactivate_all:
        return []

    return [
        e
        for e in valid_extensions
        if e.code not in settings.lnbits_deactivated_extensions
    ]


async def get_valid_extension(
    ext_id: str, include_deactivated: bool | None = True
) -> Extension | None:
    ext = await get_installed_extension(ext_id)
    if not ext:
        return None

    if include_deactivated:
        return Extension.from_installable_ext(ext)

    if settings.lnbits_extensions_deactivate_all:
        return None

    return Extension.from_installable_ext(ext)
