from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from loguru import logger

from lnbits.core.crud.extensions import get_user_extension
from lnbits.core.crud.payments import get_standalone_payment, update_payment
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models import User
from lnbits.core.models.payments import Payment
from lnbits.core.services import websocket_updater
from lnbits.db import Database
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer
from lnbits.settings import settings
from lnbits.tasks import register_invoice_listener, unregister_invoice_listener

from .service import WasmExecutionError, wasm_call


@dataclass
class TagWatch:
    ext_id: str
    user_id: str
    wallet_id: str
    tag: str
    handler: str
    store_key: str
    upgrade_hash: str | None


_tag_watchers: dict[tuple[str, str], list[TagWatch]] = {}
_TAG_WATCH_KV_KEY = "watch_tags"
_background_tasks: list[asyncio.Task] = []


@dataclass
class ScheduleTask:
    ext_id: str
    user_id: str
    handler: str
    interval_seconds: int
    store_key: str
    upgrade_hash: str | None
    next_run: float


_scheduled_tasks: dict[str, list[ScheduleTask]] = {}
_SCHEDULE_KV_KEY = "scheduled_tasks"


def _register_tag_watch(watch: TagWatch) -> None:
    key = (watch.wallet_id, watch.tag)
    existing = _tag_watchers.get(key, [])
    for item in existing:
        if (
            item.ext_id == watch.ext_id
            and item.user_id == watch.user_id
            and item.handler == watch.handler
            and item.store_key == watch.store_key
        ):
            return
    existing.append(watch)
    _tag_watchers[key] = existing


async def _load_schedule_list(db: Database, ext_id: str) -> list[dict]:
    raw = await _kv_get(db, ext_id, _SCHEDULE_KV_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


async def _save_schedule_list(db: Database, ext_id: str, items: list[dict]) -> None:
    await _kv_set(db, ext_id, _SCHEDULE_KV_KEY, json.dumps(items))


def _register_schedule(task: ScheduleTask) -> None:
    existing = _scheduled_tasks.get(task.ext_id, [])
    for item in existing:
        if (
            item.user_id == task.user_id
            and item.handler == task.handler
            and item.interval_seconds == task.interval_seconds
            and item.store_key == task.store_key
        ):
            return
    existing.append(task)
    _scheduled_tasks[task.ext_id] = existing


async def _persist_schedule(ext_id: str, task: ScheduleTask) -> None:
    db = Database(f"ext_{ext_id}")
    items = await _load_schedule_list(db, ext_id)
    for item in items:
        if (
            item.get("user_id") == task.user_id
            and item.get("handler") == task.handler
            and item.get("interval_seconds") == task.interval_seconds
            and item.get("store_key") == task.store_key
        ):
            return
    items.append(
        {
            "user_id": task.user_id,
            "handler": task.handler,
            "interval_seconds": task.interval_seconds,
            "store_key": task.store_key,
            "upgrade_hash": task.upgrade_hash,
        }
    )
    await _save_schedule_list(db, ext_id, items)


async def _remove_persisted_schedule_entries(
    ext_id: str,
    user_id: str | None = None,
    handler: str | None = None,
    store_key: str | None = None,
) -> None:
    try:
        db = Database(f"ext_{ext_id}")
        items = await _load_schedule_list(db, ext_id)
        items = [
            item
            for item in items
            if not (
                (user_id is None or item.get("user_id") == user_id)
                and (handler is None or item.get("handler") == handler)
                and (store_key is None or item.get("store_key") == store_key)
            )
        ]
        await _save_schedule_list(db, ext_id, items)
    except Exception:
        return


def _remove_schedule_entries(
    ext_id: str,
    user_id: str | None = None,
    handler: str | None = None,
    store_key: str | None = None,
) -> None:
    existing = _scheduled_tasks.get(ext_id, [])
    if not existing:
        return
    _scheduled_tasks[ext_id] = [
        item
        for item in existing
        if not (
            (user_id is None or item.user_id == user_id)
            and (handler is None or item.handler == handler)
            and (store_key is None or item.store_key == store_key)
        )
    ]
    if not _scheduled_tasks[ext_id]:
        _scheduled_tasks.pop(ext_id, None)


async def restore_schedules(ext_id: str, upgrade_hash: str | None) -> None:
    try:
        db = Database(f"ext_{ext_id}")
        items = await _load_schedule_list(db, ext_id)
        now = time.time()
        for item in items:
            user_id = item.get("user_id")
            handler = item.get("handler")
            interval_seconds = item.get("interval_seconds")
            store_key = item.get("store_key")
            if not user_id or not handler or not interval_seconds or not store_key:
                continue
            user_ext = await get_user_extension(user_id, ext_id)
            if not user_ext or not user_ext.active:
                continue
            granted = user_ext.extra.granted_permissions if user_ext.extra else []
            if "ext.tasks.schedule" not in (granted or []):
                continue
            _register_schedule(
                ScheduleTask(
                    ext_id=ext_id,
                    user_id=user_id,
                    handler=handler,
                    interval_seconds=int(interval_seconds),
                    store_key=store_key,
                    upgrade_hash=upgrade_hash,
                    next_run=now + int(interval_seconds),
                )
            )
    except Exception:
        return


def _matches_watch(
    watch: TagWatch,
    ext_id: str,
    user_id: str,
    wallet_id: str,
    tag: str,
    handler: str | None,
    store_key: str | None,
) -> bool:
    if watch.ext_id != ext_id:
        return False
    if watch.user_id != user_id:
        return False
    if watch.wallet_id != wallet_id:
        return False
    if watch.tag != tag:
        return False
    if handler is not None and watch.handler != handler:
        return False
    if store_key is not None and watch.store_key != store_key:
        return False
    return True


async def _load_tag_watch_list(db: Database, ext_id: str) -> list[dict]:
    raw = await _kv_get(db, ext_id, _TAG_WATCH_KV_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


async def _save_tag_watch_list(db: Database, ext_id: str, items: list[dict]) -> None:
    await _kv_set(db, ext_id, _TAG_WATCH_KV_KEY, json.dumps(items))


async def _persist_tag_watch(ext_id: str, watch: TagWatch) -> None:
    db = Database(f"ext_{ext_id}")
    items = await _load_tag_watch_list(db, ext_id)
    for item in items:
        if (
            item.get("user_id") == watch.user_id
            and item.get("wallet_id") == watch.wallet_id
            and item.get("tag") == watch.tag
            and item.get("handler") == watch.handler
            and item.get("store_key") == watch.store_key
        ):
            return
    items.append(
        {
            "user_id": watch.user_id,
            "wallet_id": watch.wallet_id,
            "tag": watch.tag,
            "handler": watch.handler,
            "store_key": watch.store_key,
            "upgrade_hash": watch.upgrade_hash,
        }
    )
    await _save_tag_watch_list(db, ext_id, items)


async def _remove_persisted_tag_watch(ext_id: str, watch: TagWatch) -> None:
    try:
        db = Database(f"ext_{ext_id}")
        items = await _load_tag_watch_list(db, ext_id)
        items = [
            item
            for item in items
            if not (
                item.get("user_id") == watch.user_id
                and item.get("wallet_id") == watch.wallet_id
                and item.get("tag") == watch.tag
                and item.get("handler") == watch.handler
                and item.get("store_key") == watch.store_key
            )
        ]
        await _save_tag_watch_list(db, ext_id, items)
    except Exception:
        return


async def _remove_persisted_tag_watch_entries(
    ext_id: str,
    user_id: str,
    wallet_id: str,
    tag: str,
    handler: str | None,
    store_key: str | None,
) -> None:
    try:
        db = Database(f"ext_{ext_id}")
        items = await _load_tag_watch_list(db, ext_id)
        items = [
            item
            for item in items
            if not (
                item.get("user_id") == user_id
                and item.get("wallet_id") == wallet_id
                and item.get("tag") == tag
                and (handler is None or item.get("handler") == handler)
                and (store_key is None or item.get("store_key") == store_key)
            )
        ]
        await _save_tag_watch_list(db, ext_id, items)
    except Exception:
        return


async def handle_wasm_tag_payment(payment: Payment) -> None:
    if not payment.tag or not payment.is_in:
        return
    key = (payment.wallet_id, payment.tag)
    watchers = list(_tag_watchers.get(key, []))
    if not watchers:
        return
    for watch in watchers:
        _background_tasks.append(
            asyncio.create_task(_dispatch_tag_watch(payment, watch))
        )


async def _dispatch_tag_watch(payment: Payment, watch: TagWatch) -> None:
    try:
        user_ext = await get_user_extension(watch.user_id, watch.ext_id)
        if not user_ext or not user_ext.active:
            if payment.tag:
                _remove_tag_watch(payment.wallet_id, payment.tag, watch)
            await _remove_persisted_tag_watch(watch.ext_id, watch)
            return
        granted_tags = user_ext.extra.granted_payment_tags if user_ext.extra else []
        if watch.tag not in (granted_tags or []):
            if payment.tag:
                _remove_tag_watch(payment.wallet_id, payment.tag, watch)
            await _remove_persisted_tag_watch(watch.ext_id, watch)
            return

        _check_quota(
            watch.user_id, watch.ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min
        )

        db = Database(f"ext_{watch.ext_id}")
        payload_json = json.dumps(payment.dict(exclude={"preimage"}))
        await _kv_set(db, watch.ext_id, watch.store_key, payload_json)
        await websocket_updater(f"{watch.ext_id}:{watch.store_key}", payload_json)

        watch_payload = {
            "payment_hash": payment.payment_hash,
            "store_key": watch.store_key,
            "tag": watch.tag,
        }
        await _kv_set(db, watch.ext_id, "watch_request", json.dumps(watch_payload))
        await _kv_set(db, watch.ext_id, "public_request", watch.tag)
        await wasm_call(
            watch.ext_id,
            watch.handler,
            [],
            upgrade_hash=watch.upgrade_hash,
        )
    except Exception:
        return


def _remove_tag_watch(wallet_id: str, tag: str, watch: TagWatch) -> None:
    key = (wallet_id, tag)
    existing = _tag_watchers.get(key, [])
    if not existing:
        return
    _tag_watchers[key] = [
        item
        for item in existing
        if not (
            item.ext_id == watch.ext_id
            and item.user_id == watch.user_id
            and item.handler == watch.handler
            and item.store_key == watch.store_key
        )
    ]
    if not _tag_watchers[key]:
        _tag_watchers.pop(key, None)


def _remove_tag_watch_entries(
    ext_id: str,
    user_id: str,
    wallet_id: str,
    tag: str,
    handler: str | None,
    store_key: str | None,
) -> None:
    key = (wallet_id, tag)
    existing = _tag_watchers.get(key, [])
    if not existing:
        return
    _tag_watchers[key] = [
        item
        for item in existing
        if not _matches_watch(item, ext_id, user_id, wallet_id, tag, handler, store_key)
    ]
    if not _tag_watchers[key]:
        _tag_watchers.pop(key, None)


async def clear_tag_watches_for_user(ext_id: str, user_id: str) -> None:
    keys = list(_tag_watchers.keys())
    for wallet_id, tag in keys:
        existing = _tag_watchers.get((wallet_id, tag), [])
        remaining = [
            w for w in existing if not (w.ext_id == ext_id and w.user_id == user_id)
        ]
        if remaining:
            _tag_watchers[(wallet_id, tag)] = remaining
        else:
            _tag_watchers.pop((wallet_id, tag), None)
    try:
        db = Database(f"ext_{ext_id}")
        items = await _load_tag_watch_list(db, ext_id)
        items = [item for item in items if item.get("user_id") != user_id]
        await _save_tag_watch_list(db, ext_id, items)
    except Exception:
        return


async def clear_tag_watches_for_extension(ext_id: str) -> None:
    keys = list(_tag_watchers.keys())
    for wallet_id, tag in keys:
        existing = _tag_watchers.get((wallet_id, tag), [])
        remaining = [w for w in existing if w.ext_id != ext_id]
        if remaining:
            _tag_watchers[(wallet_id, tag)] = remaining
        else:
            _tag_watchers.pop((wallet_id, tag), None)
    try:
        db = Database(f"ext_{ext_id}")
        await _save_tag_watch_list(db, ext_id, [])
    except Exception:
        return


async def clear_schedules_for_user(ext_id: str, user_id: str) -> None:
    _remove_schedule_entries(ext_id, user_id=user_id)
    await _remove_persisted_schedule_entries(ext_id, user_id=user_id)


async def clear_schedules_for_extension(ext_id: str) -> None:
    _remove_schedule_entries(ext_id)
    await _remove_persisted_schedule_entries(ext_id)


async def restore_tag_watches(ext_id: str, upgrade_hash: str | None) -> None:
    try:
        db = Database(f"ext_{ext_id}")
        items = await _load_tag_watch_list(db, ext_id)
        for item in items:
            user_id = item.get("user_id")
            wallet_id = item.get("wallet_id")
            tag = item.get("tag")
            handler = item.get("handler")
            store_key = item.get("store_key")
            if not user_id or not wallet_id or not tag or not handler or not store_key:
                continue
            user_ext = await get_user_extension(user_id, ext_id)
            if not user_ext or not user_ext.active:
                continue
            granted_tags = user_ext.extra.granted_payment_tags if user_ext.extra else []
            if tag not in (granted_tags or []):
                continue
            wallet = await get_wallet(wallet_id)
            if not wallet or wallet.user != user_id:
                continue
            _register_tag_watch(
                TagWatch(
                    ext_id=ext_id,
                    user_id=user_id,
                    wallet_id=wallet_id,
                    tag=tag,
                    handler=handler,
                    store_key=store_key,
                    upgrade_hash=upgrade_hash,
                )
            )
    except Exception:
        return


async def wasm_scheduler() -> None:
    while settings.lnbits_running:
        now = time.time()
        for _ext_id, tasks in list(_scheduled_tasks.items()):
            for task in list(tasks):
                if task.next_run > now:
                    continue
                _background_tasks.append(
                    asyncio.create_task(_dispatch_schedule_task(task))
                )
                task.next_run = now + max(1, task.interval_seconds)
        await asyncio.sleep(1)


async def _dispatch_schedule_task(task: ScheduleTask) -> None:
    try:
        user_ext = await get_user_extension(task.user_id, task.ext_id)
        if not user_ext or not user_ext.active:
            _remove_schedule_entries(
                task.ext_id, task.user_id, task.handler, task.store_key
            )
            await _remove_persisted_schedule_entries(
                task.ext_id, task.user_id, task.handler, task.store_key
            )
            return
        granted = user_ext.extra.granted_permissions if user_ext.extra else []
        if "ext.tasks.schedule" not in (granted or []):
            _remove_schedule_entries(
                task.ext_id, task.user_id, task.handler, task.store_key
            )
            await _remove_persisted_schedule_entries(
                task.ext_id, task.user_id, task.handler, task.store_key
            )
            return

        _check_quota(
            task.user_id,
            task.ext_id,
            "db",
            settings.lnbits_wasm_max_db_ops_per_min,
        )

        db = Database(f"ext_{task.ext_id}")
        payload = {"ts": time.time(), "interval_seconds": task.interval_seconds}
        await _kv_set(db, task.ext_id, task.store_key, json.dumps(payload))
        await websocket_updater(f"{task.ext_id}:{task.store_key}", json.dumps(payload))
        await wasm_call(
            task.ext_id,
            task.handler,
            [],
            upgrade_hash=task.upgrade_hash,
        )
    except Exception:
        return


def _renderer(ext_id: str):
    return template_renderer([f"{ext_id}/templates"])


def _ext_static_dir(ext_id: str, upgrade_hash: str | None = None) -> Path:
    if upgrade_hash:
        return Path(
            settings.lnbits_extensions_upgrade_path,
            f"{ext_id}-{upgrade_hash}",
            "static",
        )
    return Path(settings.lnbits_extensions_path, "extensions", ext_id, "static")


def _ensure_kv_table(db: Database, ext_id: str) -> str:
    table = _kv_table_name(db, ext_id)
    query = f"""
    CREATE TABLE IF NOT EXISTS {table} (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """
    return query


def _ensure_secret_kv_table(db: Database, ext_id: str) -> str:
    table = _secret_kv_table_name(db, ext_id)
    query = f"""
    CREATE TABLE IF NOT EXISTS {table} (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """
    return query


_kv_schema_cache: dict[str, dict] = {}


def _kv_table_name(db: Database, ext_id: str) -> str:
    table = f"{ext_id}.kv" if db.schema else "kv"
    if (
        re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?", table)
        is None
    ):
        raise ValueError("Invalid KV table name")
    return table


def _secret_kv_table_name(db: Database, ext_id: str) -> str:
    table = f"{ext_id}.secret_kv" if db.schema else "secret_kv"
    if (
        re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?", table)
        is None
    ):
        raise ValueError("Invalid secret KV table name")
    return table


def _load_kv_schema(ext_id: str) -> dict:
    if ext_id in _kv_schema_cache:
        return _kv_schema_cache[ext_id]
    try:
        conf_path = Path(
            settings.lnbits_extensions_path, "extensions", ext_id, "config.json"
        )
        if not conf_path.is_file():
            _kv_schema_cache[ext_id] = {}
            return _kv_schema_cache[ext_id]
        with open(conf_path, "r+") as json_file:
            config_json = json.load(json_file)
        schema = config_json.get("kv_schema", {})
        if not isinstance(schema, dict):
            schema = {}
        _kv_schema_cache[ext_id] = schema
        return schema
    except Exception:
        _kv_schema_cache[ext_id] = {}
        return _kv_schema_cache[ext_id]


def _load_public_wasm_functions(ext_id: str) -> list[str]:
    try:
        conf_path = Path(
            settings.lnbits_extensions_path, "extensions", ext_id, "config.json"
        )
        if not conf_path.is_file():
            return []
        with open(conf_path, "r+") as json_file:
            config_json = json.load(json_file)
        funcs = config_json.get("public_wasm_functions", [])
        return funcs if isinstance(funcs, list) else []
    except Exception:
        return []


def _schema_for_key(schema: dict, key: str) -> dict | None:
    if not schema:
        return None
    entry = schema.get(key)
    return entry if isinstance(entry, dict) else None


def _validate_sql(ext_id: str, sql: str, read_only: bool) -> None:
    statement = sql.strip().strip(";").lower()
    if ";" in statement:
        raise HTTPException(400, "Only single-statement SQL is allowed")
    if read_only:
        if not statement.startswith("select "):
            raise HTTPException(400, "Only SELECT is allowed in read-only queries")
    else:
        allowed = (
            "create table",
            "alter table",
            "insert",
            "update",
            "delete",
            "drop table",
        )
        if not any(statement.startswith(prefix) for prefix in allowed):
            raise HTTPException(400, "Statement not allowed")
    if "sqlite_master" in statement or "pragma" in statement:
        raise HTTPException(400, "Statement not allowed")
    for match in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.", statement):
        schema = match.group(1)
        if schema != ext_id:
            raise HTTPException(400, "Cross-schema access is not allowed")


def _coerce_schema_value(schema_entry: dict, value):
    value_type = schema_entry.get("type", "string")
    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "y"}
        return bool(value)
    if value_type == "json":
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            return json.loads(value)
        raise ValueError("Invalid json value")
    return str(value)


async def _kv_get(db: Database, ext_id: str, key: str) -> str | None:
    await db.execute(_ensure_kv_table(db, ext_id))
    table = _kv_table_name(db, ext_id)
    row: dict[str, Any] | None = await db.fetchone(
        f"SELECT value FROM {table} WHERE key = :key",  # noqa: S608
        {"key": key},
    )
    if not row:
        schema = _load_kv_schema(ext_id)
        entry = _schema_for_key(schema, key)
        if entry and "default" in entry:
            default_value = _coerce_schema_value(entry, entry.get("default"))
            stored = (
                json.dumps(default_value)
                if entry.get("type") == "json"
                else str(default_value)
            )
            await _kv_set(db, ext_id, key, stored)
            return stored
        return None
    return row.get("value")


async def _kv_set(db: Database, ext_id: str, key: str, value: str) -> None:
    await db.execute(_ensure_kv_table(db, ext_id))
    table = _kv_table_name(db, ext_id)
    existing: dict[str, Any] | None = await db.fetchone(
        f"SELECT key FROM {table} WHERE key = :key",  # noqa: S608
        {"key": key},
    )
    if existing:
        await db.execute(
            f"UPDATE {table} SET value = :value WHERE key = :key",  # noqa: S608
            {"key": key, "value": value},
        )
    else:
        await db.execute(
            f"INSERT INTO {table} (key, value) VALUES (:key, :value)",  # noqa: S608
            {"key": key, "value": value},
        )


async def _secret_kv_get(db: Database, ext_id: str, key: str) -> str | None:
    await db.execute(_ensure_secret_kv_table(db, ext_id))
    table = _secret_kv_table_name(db, ext_id)
    row: dict[str, Any] | None = await db.fetchone(
        f"SELECT value FROM {table} WHERE key = :key",  # noqa: S608
        {"key": key},
    )
    if not row:
        return None
    return row.get("value")


async def _secret_kv_set(db: Database, ext_id: str, key: str, value: str) -> None:
    await db.execute(_ensure_secret_kv_table(db, ext_id))
    table = _secret_kv_table_name(db, ext_id)
    existing: dict[str, Any] | None = await db.fetchone(
        f"SELECT key FROM {table} WHERE key = :key",  # noqa: S608
        {"key": key},
    )
    if existing:
        await db.execute(
            f"UPDATE {table} SET value = :value WHERE key = :key",  # noqa: S608
            {"key": key, "value": value},
        )
    else:
        await db.execute(
            f"INSERT INTO {table} (key, value) VALUES (:key, :value)",  # noqa: S608
            {"key": key, "value": value},
        )


async def _secret_kv_delete(db: Database, ext_id: str, key: str) -> None:
    await db.execute(_ensure_secret_kv_table(db, ext_id))
    table = _secret_kv_table_name(db, ext_id)
    await db.execute(
        f"DELETE FROM {table} WHERE key = :key",  # noqa: S608
        {"key": key},
    )


async def _require_permission(user_id: str, ext_id: str, permission: str) -> None:
    user_ext = await get_user_extension(user_id, ext_id)
    if not user_ext or not user_ext.active:
        raise HTTPException(403, "Extension not enabled.")
    granted = user_ext.extra.granted_permissions if user_ext.extra else []
    if permission not in (granted or []):
        raise HTTPException(403, f"Missing permission: {permission}")


async def _require_payment_tag(user_id: str, ext_id: str, tag: str) -> None:
    user_ext = await get_user_extension(user_id, ext_id)
    if not user_ext or not user_ext.active:
        raise HTTPException(403, "Extension not enabled.")
    granted = user_ext.extra.granted_payment_tags if user_ext.extra else []
    if tag not in (granted or []):
        raise HTTPException(403, f"Missing payment tag permission: {tag}")


def _register_pages_routes(router: APIRouter, ext_id: str) -> None:
    @router.get("/", response_class=HTMLResponse)
    async def index(req: Request, user: User = Depends(check_user_exists)):
        try:
            return _renderer(ext_id).TemplateResponse(
                f"{ext_id}/index.html",
                {"request": req, "user": user.json()},
            )
        except Exception:
            return HTMLResponse("Extension page not found", status_code=404)

    @router.get("/public/{key}", response_class=HTMLResponse)
    async def public_page(req: Request, key: str):
        try:
            return _renderer(ext_id).TemplateResponse(
                f"{ext_id}/public_page.html",
                {"request": req, "key": key, "public": True},
            )
        except Exception:
            return HTMLResponse("Public page not found", status_code=404)


def _register_kv_routes(router: APIRouter, ext_id: str, db: Database, ext) -> None:
    _register_kv_read_routes(router, ext_id, db, ext)
    _register_kv_write_routes(router, ext_id, db)
    _register_secret_routes(router, ext_id, db)


def _register_secret_routes(router: APIRouter, ext_id: str, db: Database) -> None:
    @router.post("/api/v1/secret/{key}")
    async def api_secret_set(
        key: str, payload: dict, user: User = Depends(check_user_exists)
    ):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        value = payload.get("value")
        if value is None:
            raise HTTPException(400, "Missing value")
        await _secret_kv_set(db, ext_id, key, str(value))
        return {"key": key}

    @router.delete("/api/v1/secret/{key}")
    async def api_secret_delete(key: str, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        await _secret_kv_delete(db, ext_id, key)
        return {"key": key}


def _register_public_call_routes(
    router: APIRouter, ext_id: str, db: Database, ext
) -> None:
    @router.post("/api/v1/public/call/{handler}")
    async def api_public_wasm_call(handler: str, payload: dict):
        funcs = getattr(
            ext, "public_wasm_functions", None
        ) or _load_public_wasm_functions(ext_id)
        if handler not in funcs:
            raise HTTPException(404, "Handler not public")
        _check_quota("public", ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)

        request_id = int(time.time() * 1000) % 2147483647
        raw = payload.get("raw")
        value = raw if isinstance(raw, str) else json.dumps(payload)
        await _kv_set(db, ext_id, f"public_request:{request_id}", value)
        await _kv_set(db, ext_id, "public_request", value)

        try:
            await wasm_call(
                ext_id, handler, [request_id], upgrade_hash=ext.upgrade_hash
            )
        except WasmExecutionError as exc:
            raise HTTPException(500, str(exc)) from exc

        response = await _kv_get(db, ext_id, f"public_response:{request_id}")
        if response is None:
            response = await _kv_get(db, ext_id, "public_response")
        if response is None:
            raise HTTPException(500, "No response")
        try:
            data = json.loads(response)
        except Exception:
            return {"raw": response}

        watch = payload.get("watch") if isinstance(payload, dict) else None
        if isinstance(watch, dict) and isinstance(data, dict):
            payment_hash = data.get("payment_hash")
            store_key = watch.get("store_key")
            tag = watch.get("tag")
            handler_name = watch.get("handler") or "noop"
            if (
                isinstance(payment_hash, str)
                and isinstance(store_key, str)
                and handler_name in funcs
            ):
                _start_payment_watch(
                    ext_id,
                    db,
                    payment_hash,
                    handler_name,
                    tag if isinstance(tag, str) else None,
                    store_key,
                    ext.upgrade_hash,
                )

        return data


def _register_kv_read_routes(router: APIRouter, ext_id: str, db: Database, ext) -> None:
    @router.get("/api/v1/kv/{key}")
    async def api_kv_get(key: str, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        value = await _kv_get(db, ext_id, key)
        return {"key": key, "value": value}

    @router.get("/api/v1/public/kv/{key}")
    async def api_kv_get_public(key: str):
        public_keys = ext.public_kv_keys or []
        if key not in public_keys:
            raise HTTPException(404, "Key not public")
        _check_quota("public", ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        value = await _kv_get(db, ext_id, key)
        return {"key": key, "value": value}


def _register_kv_write_routes(router: APIRouter, ext_id: str, db: Database) -> None:
    @router.post("/api/v1/kv/{key}")
    async def api_kv_set(
        key: str, payload: dict, user: User = Depends(check_user_exists)
    ):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        value = payload.get("value")
        if value is None:
            raise HTTPException(400, "Missing value")
        schema = _load_kv_schema(ext_id)
        entry = _schema_for_key(schema, key)
        if schema and not entry:
            raise HTTPException(400, "Key not allowed by schema")
        if entry:
            try:
                coerced = _coerce_schema_value(entry, value)
            except Exception:
                raise HTTPException(400, "Invalid value for schema") from None
            value = json.dumps(coerced) if entry.get("type") == "json" else str(coerced)
        await _kv_set(db, ext_id, key, str(value))
        await websocket_updater(f"{ext_id}:{key}", str(value))
        return {"key": key, "value": value}


def _register_watch_routes(  # noqa: C901
    router: APIRouter, ext_id: str, db: Database, ext
) -> None:
    @router.post("/api/v1/watch")
    async def api_watch_payment(payload: dict, user: User = Depends(check_user_exists)):
        payment_hash = payload.get("payment_hash")
        handler = payload.get("handler") or "on_payment"
        tag = payload.get("tag")
        store_key = payload.get("store_key") or "last_payment"
        if not payment_hash:
            raise HTTPException(400, "Missing payment_hash")
        await _require_permission(user.id, ext_id, "ext.payments.watch")
        if tag:
            await _require_payment_tag(user.id, ext_id, tag)
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        task = _start_payment_watch(
            ext_id, db, payment_hash, handler, tag, store_key, ext.upgrade_hash
        )
        return {"ok": True, "task_id": id(task)}

    @router.post("/api/v1/watch_tag")
    async def api_watch_tag(payload: dict, user: User = Depends(check_user_exists)):
        tag = payload.get("tag")
        handler = payload.get("handler") or "on_tag_payment"
        store_key = payload.get("store_key")
        wallet_id = payload.get("wallet_id")
        if not tag:
            raise HTTPException(400, "Missing tag")
        if not wallet_id:
            raise HTTPException(400, "Missing wallet_id")
        await _require_permission(user.id, ext_id, "ext.payments.watch")
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        await _require_payment_tag(user.id, ext_id, tag)
        wallet = await get_wallet(wallet_id)
        if not wallet or wallet.user != user.id:
            raise HTTPException(403, "Wallet not found or not owned by user")

        funcs = getattr(
            ext, "public_wasm_functions", None
        ) or _load_public_wasm_functions(ext_id)
        if handler not in funcs:
            raise HTTPException(400, "Handler not allowed")

        if not store_key:
            store_key = f"tag:{tag}:last_payment"

        _register_tag_watch(
            TagWatch(
                ext_id=ext_id,
                user_id=user.id,
                wallet_id=wallet_id,
                tag=tag,
                handler=handler,
                store_key=store_key,
                upgrade_hash=ext.upgrade_hash,
            )
        )
        await _persist_tag_watch(
            ext_id,
            TagWatch(
                ext_id=ext_id,
                user_id=user.id,
                wallet_id=wallet_id,
                tag=tag,
                handler=handler,
                store_key=store_key,
                upgrade_hash=ext.upgrade_hash,
            ),
        )

        return {"ok": True}

    @router.delete("/api/v1/watch_tag")
    async def api_watch_tag_delete(
        payload: dict, user: User = Depends(check_user_exists)
    ):
        tag = payload.get("tag")
        wallet_id = payload.get("wallet_id")
        handler = payload.get("handler")
        store_key = payload.get("store_key")
        if not tag:
            raise HTTPException(400, "Missing tag")
        if not wallet_id:
            raise HTTPException(400, "Missing wallet_id")
        await _require_permission(user.id, ext_id, "ext.payments.watch")
        wallet = await get_wallet(wallet_id)
        if not wallet or wallet.user != user.id:
            raise HTTPException(403, "Wallet not found or not owned by user")
        _remove_tag_watch_entries(ext_id, user.id, wallet_id, tag, handler, store_key)
        await _remove_persisted_tag_watch_entries(
            ext_id, user.id, wallet_id, tag, handler, store_key
        )
        return {"ok": True}

    @router.post("/api/v1/schedule")
    async def api_schedule_task(payload: dict, user: User = Depends(check_user_exists)):
        interval_seconds = payload.get("interval_seconds")
        handler = payload.get("handler") or "on_schedule"
        store_key = payload.get("store_key") or "schedule:last_run"
        if not interval_seconds:
            raise HTTPException(400, "Missing interval_seconds")
        try:
            interval_seconds = int(interval_seconds)
        except Exception:
            raise HTTPException(400, "Invalid interval_seconds") from None
        if interval_seconds < 5:
            raise HTTPException(400, "Minimum interval is 5 seconds")

        await _require_permission(user.id, ext_id, "ext.tasks.schedule")
        await _require_permission(user.id, ext_id, "ext.db.read_write")

        funcs = getattr(
            ext, "public_wasm_functions", None
        ) or _load_public_wasm_functions(ext_id)
        if handler not in funcs:
            raise HTTPException(400, "Handler not allowed")

        task = ScheduleTask(
            ext_id=ext_id,
            user_id=user.id,
            handler=handler,
            interval_seconds=interval_seconds,
            store_key=store_key,
            upgrade_hash=ext.upgrade_hash,
            next_run=time.time() + interval_seconds,
        )
        _register_schedule(task)
        await _persist_schedule(ext_id, task)
        return {"ok": True}

    @router.delete("/api/v1/schedule")
    async def api_schedule_task_delete(
        payload: dict, user: User = Depends(check_user_exists)
    ):
        handler = payload.get("handler")
        store_key = payload.get("store_key")
        await _require_permission(user.id, ext_id, "ext.tasks.schedule")
        _remove_schedule_entries(ext_id, user.id, handler, store_key)
        await _remove_persisted_schedule_entries(ext_id, user.id, handler, store_key)
        return {"ok": True}

    @router.post("/api/v1/sql/query")
    async def api_sql_query(
        payload: dict, user: User = Depends(check_user_exists)
    ) -> dict:
        sql = payload.get("sql")
        params = payload.get("params") or {}
        if not sql:
            raise HTTPException(400, "Missing sql")
        await _require_permission(user.id, ext_id, "ext.db.sql")
        _check_quota(user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        _validate_sql(ext_id, sql, read_only=True)
        rows: list[dict] = await db.fetchall(sql, params)
        return {"rows": rows}

    @router.post("/api/v1/sql/exec")
    async def api_sql_exec(
        payload: dict, user: User = Depends(check_user_exists)
    ) -> dict:
        sql = payload.get("sql")
        params = payload.get("params") or {}
        if not sql:
            raise HTTPException(400, "Missing sql")
        await _require_permission(user.id, ext_id, "ext.db.sql")
        _check_quota(user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        _validate_sql(ext_id, sql, read_only=False)
        await db.execute(sql, params)
        return {"ok": True}


def _start_payment_watch(  # noqa: C901
    ext_id: str,
    db: Database,
    payment_hash: str,
    handler: str,
    tag: str | None,
    store_key: str,
    upgrade_hash: str | None,
) -> asyncio.Task:
    queue_name = f"wasm:{ext_id}:{payment_hash}:{time.time()}"
    invoice_queue: asyncio.Queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, queue_name)
    logger.debug(
        f"wasm watch registered ext={ext_id} hash={payment_hash} store_key={store_key}"
    )

    async def _watch():
        try:
            existing = await get_standalone_payment(payment_hash, incoming=True)
            if existing and existing.pending is False:
                logger.debug(
                    f"wasm watch already paid ext={ext_id} hash={payment_hash}"
                )
                if tag:
                    extra = existing.extra or {}
                    if extra.get("tag") != tag:
                        extra["tag"] = tag
                        existing.extra = extra
                        existing.tag = tag
                        await update_payment(existing)
                payload_json = json.dumps(existing.dict(exclude={"preimage"}))
                await _kv_set(db, ext_id, store_key, payload_json)
                await websocket_updater(f"{ext_id}:{store_key}", payload_json)
                watch_payload = {
                    "payment_hash": payment_hash,
                    "store_key": store_key,
                    "tag": tag,
                }
                await _kv_set(db, ext_id, "watch_request", json.dumps(watch_payload))
                watch_value = store_key.rsplit(":", 1)[-1]
                await _kv_set(db, ext_id, "public_request", watch_value)
                await wasm_call(
                    ext_id,
                    handler,
                    [],
                    upgrade_hash=upgrade_hash,
                )
                return
            while True:
                payment = await invoice_queue.get()
                if payment.payment_hash != payment_hash:
                    continue
                logger.debug(
                    "wasm watch event ext=%s hash=%s pending=%s",
                    ext_id,
                    payment_hash,
                    payment.pending,
                )
                if tag:
                    extra = payment.extra or {}
                    if extra.get("tag") != tag:
                        extra["tag"] = tag
                        payment.extra = extra
                        payment.tag = tag
                        await update_payment(payment)
                if payment.pending is False:
                    payload_json = json.dumps(payment.dict(exclude={"preimage"}))
                    await _kv_set(db, ext_id, store_key, payload_json)
                    await websocket_updater(f"{ext_id}:{store_key}", payload_json)
                    watch_payload = {
                        "payment_hash": payment_hash,
                        "store_key": store_key,
                        "tag": tag,
                    }
                    await _kv_set(
                        db, ext_id, "watch_request", json.dumps(watch_payload)
                    )
                    watch_value = store_key.rsplit(":", 1)[-1]
                    await _kv_set(db, ext_id, "public_request", watch_value)
                    await wasm_call(
                        ext_id,
                        handler,
                        [],
                        upgrade_hash=upgrade_hash,
                    )
                    return
        except Exception:
            return
        finally:
            unregister_invoice_listener(queue_name)

    return asyncio.create_task(_watch())


def _register_proxy_routes(
    router: APIRouter, app, ext_id: str, proxy_block: str
) -> None:
    @router.post("/api/v1/proxy")
    async def api_proxy(
        payload: dict, req: Request, user: User = Depends(check_user_exists)
    ):
        method = str(payload.get("method", "GET")).upper()
        path = str(payload.get("path", "")).strip()
        if not path.startswith("/") or "://" in path:
            raise HTTPException(400, "Invalid path")
        if path.startswith(proxy_block):
            raise HTTPException(400, "Proxy loop blocked")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise HTTPException(400, "Unsupported method")

        await _require_permission(user.id, ext_id, f"api.{method}:{path}")

        headers = {}
        for key in ("x-api-key", "authorization", "content-type", "accept"):
            if key in req.headers:
                headers[key] = req.headers[key]

        query = payload.get("query") or {}
        body = payload.get("body")

        async with httpx.AsyncClient(app=app, base_url="http://lnbits") as client:
            resp = await client.request(
                method, path, params=query, json=body, headers=headers
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type"),
        )


def _mount_static(app, ext_id: str, upgrade_hash: str | None) -> None:
    static_dir = _ext_static_dir(ext_id, upgrade_hash)
    if static_dir.is_dir():
        app.mount(
            f"/{ext_id}/static",
            StaticFiles(directory=static_dir),
            name=f"{ext_id}_static",
        )


def register_wasm_ext_routes(app, ext) -> None:
    ext_id = ext.code
    db = Database(f"ext_{ext_id}")
    router = APIRouter(prefix=f"/{ext_id}", tags=[f"{ext_id} (wasm)"])
    proxy_block = f"/{ext_id}/api/v1/proxy"

    _register_pages_routes(router, ext_id)
    _register_kv_routes(router, ext_id, db, ext)
    _register_public_call_routes(router, ext_id, db, ext)
    _register_watch_routes(router, ext_id, db, ext)
    _register_proxy_routes(router, app, ext_id, proxy_block)
    _mount_static(app, ext_id, ext.upgrade_hash)

    prefix = f"/upgrades/{ext.upgrade_hash}" if ext.upgrade_hash else ""
    app.include_router(router, prefix=prefix)
    _background_tasks.append(
        asyncio.create_task(restore_tag_watches(ext_id, ext.upgrade_hash))
    )
    _background_tasks.append(
        asyncio.create_task(restore_schedules(ext_id, ext.upgrade_hash))
    )


_quota_events: dict[tuple[str, str, str], list[float]] = {}


def _check_quota(user_id: str, ext_id: str, action: str, limit: int) -> None:
    if limit <= 0:
        return
    now = time.time()
    key = (user_id, ext_id, action)
    events = _quota_events.get(key, [])
    events = [t for t in events if now - t < 60]
    if len(events) >= limit:
        raise HTTPException(429, "WASM quota exceeded")
    events.append(now)
    _quota_events[key] = events
