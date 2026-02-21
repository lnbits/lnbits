from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from lnbits.core.crud.extensions import get_user_extension
from lnbits.core.crud.wallets import get_wallet_for_key, get_wallets_ids
from lnbits.core.models import User
from lnbits.core.services import create_invoice, pay_invoice, websocket_updater
from lnbits.decorators import check_user_exists
from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.settings import settings
from lnbits.tasks import register_invoice_listener, unregister_invoice_listener
from .service import WasmExecutionError, wasm_call


def _renderer(ext_id: str):
    return template_renderer([f"{ext_id}/templates"])


def _ext_static_dir(ext_id: str, upgrade_hash: str | None = None) -> Path:
    if upgrade_hash:
        return Path(
            settings.lnbits_extensions_upgrade_path, f"{ext_id}-{upgrade_hash}", "static"
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


async def _kv_get(db: Database, ext_id: str, key: str) -> str | None:
    await db.execute(_ensure_kv_table(db, ext_id))
    table = f"{ext_id}.kv" if db.schema else "kv"
    row = await db.fetchone(
        f"SELECT value FROM {table} WHERE key = :key",
        {"key": key},
    )
    if not row:
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


async def _require_wallet_access(user_id: str, wallet_id: str) -> None:
    wallet_ids = await get_wallets_ids(user_id, deleted=False)
    if wallet_id not in wallet_ids:
        raise HTTPException(403, "Wallet does not belong to user.")


def register_wasm_ext_routes(app, ext) -> None:
    ext_id = ext.code
    db = Database(f"ext_{ext_id}")
    router = APIRouter(prefix=f"/{ext_id}", tags=[f"{ext_id} (wasm)"])

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

    @router.get("/api/v1/kv/{key}")
    async def api_kv_get(key: str, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(
            user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min
        )
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
    async def api_kv_set(key: str, payload: dict, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(
            user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min
        )
        value = payload.get("value")
        if value is None:
            raise HTTPException(400, "Missing value")
        await _kv_set(db, ext_id, key, str(value))
        await websocket_updater(f"{ext_id}:{key}", str(value))
        return {"key": key, "value": value}

    @router.post("/api/v1/kv/{key}/increment")
    async def api_kv_increment(key: str, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "ext.db.read_write")
        _check_quota(
            user.id, ext_id, "db", settings.lnbits_wasm_max_db_ops_per_min
        )
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

    @router.post("/api/v1/invoices")
    async def api_create_invoice(payload: dict, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "lnbits.invoice.create")
        _check_quota(
            user.id, ext_id, "invoice", settings.lnbits_wasm_max_invoice_ops_per_min
        )
        wallet_id = payload.get("wallet_id")
        amount = payload.get("amount")
        memo = payload.get("memo") or f"{ext_id} invoice"
        if not wallet_id or not amount:
            raise HTTPException(400, "Missing wallet_id or amount")
        await _require_wallet_access(user.id, wallet_id)

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid amount")

        payment = await create_invoice(wallet_id=wallet_id, amount=amount, memo=memo)
        return {
            "payment_hash": payment.payment_hash,
            "payment_request": payment.bolt11,
            "amount": payment.amount,
        }

    @router.post("/api/v1/invoices/pay")
    async def api_pay_invoice(payload: dict, user: User = Depends(check_user_exists)):
        await _require_permission(user.id, ext_id, "lnbits.invoice.pay")
        _check_quota(
            user.id, ext_id, "invoice", settings.lnbits_wasm_max_invoice_ops_per_min
        )
        wallet_id = payload.get("wallet_id")
        payment_request = payload.get("payment_request")
        if not wallet_id or not payment_request:
            raise HTTPException(400, "Missing wallet_id or payment_request")
        await _require_wallet_access(user.id, wallet_id)

        payment = await pay_invoice(
            wallet_id=wallet_id,
            payment_request=payment_request,
            description=f"{ext_id} payment",
            tag=ext_id,
        )
        return {
            "payment_hash": payment.payment_hash,
            "amount_msat": payment.amount_msat,
            "status": payment.status,
        }

    @router.websocket("/api/v1/events/ws")
    async def events_ws(websocket: WebSocket, api_key: str = Query(default="")):
        await websocket.accept()
        wallet = await get_wallet_for_key(api_key) if api_key else None
        if not wallet:
            await websocket.close(code=1008)
            return
        try:
            await _require_permission(wallet.user, ext_id, "lnbits.payments.subscribe")
        except HTTPException:
            await websocket.close(code=1008)
            return

        wallet_ids = await get_wallets_ids(wallet.user, deleted=False)
        queue_name = f"wasm:{ext_id}:{wallet.user}:{id(websocket)}"
        invoice_queue: asyncio.Queue = asyncio.Queue()
        register_invoice_listener(invoice_queue, queue_name)

        try:
            while True:
                payment = await invoice_queue.get()
                if payment.wallet_id in wallet_ids:
                    await websocket.send_json(payment.dict())
        except Exception:
            pass
        finally:
            unregister_invoice_listener(queue_name)

    static_dir = _ext_static_dir(ext_id, ext.upgrade_hash)
    if static_dir.is_dir():
        app.mount(
            f"/{ext_id}/static",
            StaticFiles(directory=static_dir),
            name=f"{ext_id}_static",
        )

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
