from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from lnbits.core.crud.extensions import get_user_extension
from lnbits.core.models import User
from lnbits.core.services import websocket_updater
from lnbits.db import Database
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer
from lnbits.settings import settings
from lnbits.tasks import register_invoice_listener, unregister_invoice_listener

from .service import WasmExecutionError, wasm_call


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
    table = f"{ext_id}.kv" if db.schema else "kv"
    query = f"""
    CREATE TABLE IF NOT EXISTS {table} (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """
    return query


_kv_schema_cache: dict[str, dict] = {}


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


def _schema_for_key(schema: dict, key: str) -> dict | None:
    if not schema:
        return None
    entry = schema.get(key)
    return entry if isinstance(entry, dict) else None


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
    table = f"{ext_id}.kv" if db.schema else "kv"
    row = await db.fetchone(
        f"SELECT value FROM {table} WHERE key = :key",
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
    table = f"{ext_id}.kv" if db.schema else "kv"
    existing = await db.fetchone(
        f"SELECT key FROM {table} WHERE key = :key",
        {"key": key},
    )
    if existing:
        await db.execute(
            f"UPDATE {table} SET value = :value WHERE key = :key",
            {"key": key, "value": value},
        )
    else:
        await db.execute(
            f"INSERT INTO {table} (key, value) VALUES (:key, :value)",
            {"key": key, "value": value},
        )


async def _require_permission(user_id: str, ext_id: str, permission: str) -> None:
    user_ext = await get_user_extension(user_id, ext_id)
    if not user_ext or not user_ext.active:
        raise HTTPException(403, "Extension not enabled.")
    granted = user_ext.extra.granted_permissions if user_ext.extra else []
    if permission not in (granted or []):
        raise HTTPException(403, f"Missing permission: {permission}")


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

    @router.post("/api/v1/kv/{key}/increment")
    async def api_kv_increment(key: str, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min)
        if key != "counter":
            raise HTTPException(400, "Only 'counter' is supported in this example.")
        try:
            new_value = await wasm_call(
                ext_id, "increment_counter", [], upgrade_hash=ext.upgrade_hash
            )
        except WasmExecutionError as exc:
            raise HTTPException(500, str(exc)) from exc
        await _kv_set(db, ext_id, key, str(new_value))
        await websocket_updater(f"{ext_id}:{key}", str(new_value))
        return {"key": key, "value": new_value}


def _register_watch_routes(router: APIRouter, ext_id: str, db: Database, ext) -> None:
    @router.post("/api/v1/watch")
    async def api_watch_payment(payload: dict, user: User = Depends(check_user_exists)):
        payment_hash = payload.get("payment_hash")
        handler = payload.get("handler") or "on_payment"
        tag = payload.get("tag")
        store_key = payload.get("store_key") or "last_payment"
        if not payment_hash:
            raise HTTPException(400, "Missing payment_hash")
        await _require_permission(user.id, ext_id, "ext.payments.watch")
        await _require_permission(user.id, ext_id, "ext.db.read_write")

        queue_name = f"wasm:{ext_id}:{payment_hash}:{time.time()}"
        invoice_queue: asyncio.Queue = asyncio.Queue()
        register_invoice_listener(invoice_queue, queue_name)

        async def _watch():
            try:
                while True:
                    payment = await invoice_queue.get()
                    if payment.payment_hash != payment_hash:
                        continue
                    if tag:
                        extra = payment.extra or {}
                        if extra.get("tag") != tag:
                            continue
                    if payment.pending is False:
                        payload_json = json.dumps(payment.dict(exclude={"preimage"}))
                        await _kv_set(db, ext_id, store_key, payload_json)
                        await wasm_call(
                            ext_id,
                            handler,
                            [],
                            upgrade_hash=ext.upgrade_hash,
                        )
                        return
            except Exception:
                return
            finally:
                unregister_invoice_listener(queue_name)

        task = asyncio.create_task(_watch())
        return {"ok": True, "task_id": id(task)}


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
    _register_watch_routes(router, ext_id, db, ext)
    _register_proxy_routes(router, app, ext_id, proxy_block)
    _mount_static(app, ext_id, ext.upgrade_hash)

    prefix = f"/upgrades/{ext.upgrade_hash}" if ext.upgrade_hash else ""
    app.include_router(router, prefix=prefix)


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
